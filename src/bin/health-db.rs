use std::{env, process::ExitCode};

use anyhow::{Context, Result, bail};
use sqlx::{PgPool, postgres::PgPoolOptions};

const BASE_SCHEMA: &str = include_str!("../../db/schema.sql");
const DEVELOPMENT_FIXTURE: &str = include_str!("../../db/fixtures/development.sql");
const DEFAULT_DATABASE_URL: &str = "postgres://health:health@127.0.0.1:5432/health";
const REQUIRED_CATALOG_TABLES: i64 = 2;

#[tokio::main]
async fn main() -> ExitCode {
    match run().await {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("error: {error:#}");
            ExitCode::FAILURE
        }
    }
}

async fn run() -> Result<()> {
    let command = env::args().nth(1).unwrap_or_else(|| "help".to_owned());

    if matches!(command.as_str(), "help" | "--help" | "-h") {
        print_help();
        return Ok(());
    }

    let database_url = env::var("DATABASE_URL").unwrap_or_else(|_| DEFAULT_DATABASE_URL.to_owned());
    let pool = PgPoolOptions::new()
        .max_connections(5)
        .connect(&database_url)
        .await
        .context("connect to PostgreSQL using DATABASE_URL")?;

    match command.as_str() {
        "bootstrap" => bootstrap(&pool).await,
        "status" => status(&pool).await,
        "load-fixture" => load_fixture(&pool).await,
        "verify" => verify(&pool).await,
        unknown => bail!("unknown command {unknown:?}; run health-db help"),
    }
}

async fn status(pool: &PgPool) -> Result<()> {
    match catalog_table_count(pool).await? {
        0 => println!("base schema is not installed"),
        REQUIRED_CATALOG_TABLES => {
            println!("base schema is installed");
            println!("migration history has not started (pre-deployment)");
        }
        count => bail!(
            "database schema differs from the current baseline: expected \
             {REQUIRED_CATALOG_TABLES} tables, found {count}; reset the disposable database"
        ),
    }

    Ok(())
}

async fn bootstrap(pool: &PgPool) -> Result<()> {
    match catalog_table_count(pool).await? {
        REQUIRED_CATALOG_TABLES => {
            println!("base schema is already installed");
            return Ok(());
        }
        0 => {}
        count => bail!(
            "refusing to bootstrap a database with {count} public tables; \
             expected an empty database or the {REQUIRED_CATALOG_TABLES}-table baseline"
        ),
    }

    let public_table_count: i64 = sqlx::query_scalar(
        "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'",
    )
    .fetch_one(pool)
    .await
    .context("inspect public schema")?;

    if public_table_count != 0 {
        bail!("refusing to bootstrap a non-empty public schema ({public_table_count} tables)");
    }

    sqlx::raw_sql(BASE_SCHEMA)
        .execute(pool)
        .await
        .context("install base schema")?;
    println!("base schema installed");
    Ok(())
}

async fn load_fixture(pool: &PgPool) -> Result<()> {
    bootstrap(pool).await?;
    sqlx::raw_sql(DEVELOPMENT_FIXTURE)
        .execute(pool)
        .await
        .context("load development fixture")?;
    println!("development fixture loaded");
    Ok(())
}

async fn verify(pool: &PgPool) -> Result<()> {
    let required_tables = catalog_table_count(pool).await?;

    if required_tables != REQUIRED_CATALOG_TABLES {
        bail!("expected {REQUIRED_CATALOG_TABLES} catalog tables, found {required_tables}");
    }

    let food_count: i64 = sqlx::query_scalar("SELECT count(*) FROM foods")
        .fetch_one(pool)
        .await?;
    let source_count: i64 =
        sqlx::query_scalar("SELECT count(*) FROM food_sources WHERE source_name = 'BLS 4.0'")
            .fetch_one(pool)
            .await?;
    let raw_nutrient_count: i64 = sqlx::query_scalar(
        "SELECT count(*) \
         FROM food_sources AS source \
         CROSS JOIN LATERAL jsonb_each(source.raw_data->'nutrients') AS nutrient \
         WHERE source.source_name = 'BLS 4.0'",
    )
    .fetch_one(pool)
    .await?;
    let logical_zero_count: i64 = sqlx::query_scalar(
        "SELECT count(*) FROM food_sources \
         WHERE source_name = 'BLS 4.0' AND vitamin_b12_ug = 0 \
         AND raw_data #>> '{nutrients,VITB12,provenance}' = 'logical_zero'",
    )
    .fetch_one(pool)
    .await?;
    let missing_count: i64 = sqlx::query_scalar(
        "SELECT count(*) FROM food_sources \
         WHERE source_name = 'BLS 4.0' AND beta_carotene_ug IS NULL \
         AND raw_data #>> '{nutrients,CARTB,state}' = 'missing'",
    )
    .fetch_one(pool)
    .await?;
    let below_limit_count: i64 = sqlx::query_scalar(
        "SELECT count(*) FROM food_sources \
         WHERE source_name = 'BLS 4.0' AND vitamin_c_mg IS NULL \
         AND raw_data #>> '{nutrients,VITC,state}' = \
             'below_detection_or_quantification_limit'",
    )
    .fetch_one(pool)
    .await?;
    let representative_count: i64 = sqlx::query_scalar(
        "SELECT count(*) FROM food_sources AS source \
         JOIN foods AS food ON food.id = source.food_id \
         WHERE source.source_name = 'BLS 4.0' \
         AND (
             (food.slug = 'apple-raw' AND source.external_id = 'F110100'
                 AND source.energy_kcal = 58 AND source.protein_g = 0.424)
             OR (food.slug = 'white-rice-raw' AND source.external_id = 'C352000'
                 AND source.carbs_g = 77.1)
             OR (food.slug = 'lentil-mature-dry' AND source.external_id = 'H725100'
                 AND source.fiber_g = 17.6)
         )",
    )
    .fetch_one(pool)
    .await?;
    let source_provenance_count: i64 = sqlx::query_scalar(
        "SELECT count(*) \
         FROM food_sources AS source \
         CROSS JOIN LATERAL jsonb_each(source.raw_data->'nutrients') AS nutrient \
         WHERE source.source_name = 'BLS 4.0' \
         AND nutrient.value->>'provenance' IS NOT NULL",
    )
    .fetch_one(pool)
    .await?;

    if food_count < 3 || source_count < 3 || raw_nutrient_count < 22 || representative_count != 3 {
        bail!(
            "fixture is incomplete: foods={food_count}, sources={source_count}, \
             raw_nutrients={raw_nutrient_count}, representative={representative_count}"
        );
    }
    if missing_count < 1 || below_limit_count < 1 {
        bail!("fixture does not demonstrate missing and below-limit values");
    }
    if logical_zero_count < 1 {
        bail!("fixture does not demonstrate a logical zero");
    }
    if source_provenance_count < raw_nutrient_count {
        bail!("fixture does not preserve source provenance for every nutrient observation");
    }

    println!(
        "schema verified: foods={food_count} sources={source_count} \
         raw_nutrients={raw_nutrient_count} missing={missing_count} \
         below_limit={below_limit_count} logical_zero={logical_zero_count}"
    );
    Ok(())
}

async fn catalog_table_count(pool: &PgPool) -> Result<i64> {
    sqlx::query_scalar(
        "SELECT count(*) FROM information_schema.tables \
         WHERE table_schema = 'public' AND table_type = 'BASE TABLE'",
    )
    .fetch_one(pool)
    .await
    .context("inspect catalog tables")
}

fn print_help() {
    println!(
        "health-db <command>\n\n\
         Commands:\n\
           bootstrap     Install the base schema into an empty database\n\
           status        Show base-schema status\n\
           load-fixture  Bootstrap and load the idempotent development fixture\n\
           verify        Verify the base schema and development fixture\n\n\
         DATABASE_URL defaults to {DEFAULT_DATABASE_URL}"
    );
}
