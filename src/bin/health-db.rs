use std::{collections::HashMap, env, process::ExitCode};

use anyhow::{Context, Result, bail};
use sqlx::{PgPool, Row, postgres::PgPoolOptions};

const BASE_SCHEMA: &str = include_str!("../../db/schema.sql");
const DEVELOPMENT_FIXTURE: &str = include_str!("../../db/fixtures/development.sql");
const DEFAULT_DATABASE_URL: &str = "postgres://health:health@127.0.0.1:5432/health";
const REQUIRED_CATALOG_TABLES: i64 = 4;

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
            "database is partially initialized: found {count} of \
             {REQUIRED_CATALOG_TABLES} catalog tables"
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
            "refusing to bootstrap a partially initialized database: found {count} of \
             {REQUIRED_CATALOG_TABLES} catalog tables"
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
    let nutrient_rows: i64 = sqlx::query_scalar("SELECT count(*) FROM nutrient_values")
        .fetch_one(pool)
        .await?;
    let state_counts: HashMap<String, i64> = sqlx::query(
        "SELECT value_state, count(*) AS count \
         FROM nutrient_values GROUP BY value_state",
    )
    .fetch_all(pool)
    .await?
    .into_iter()
    .map(|row| Ok((row.try_get("value_state")?, row.try_get("count")?)))
    .collect::<Result<_, sqlx::Error>>()?;
    let logical_zero_count: i64 = sqlx::query_scalar(
        "SELECT count(*) FROM nutrient_values \
         WHERE source_provenance = 'logical_zero' AND amount = 0",
    )
    .fetch_one(pool)
    .await?;
    let source_provenance_count: i64 = sqlx::query_scalar(
        "SELECT count(*) \
         FROM nutrient_values AS value \
         JOIN food_sources AS source \
             ON source.id = value.food_source_id \
         WHERE source.source_name = 'BLS 4.0' AND value.source_provenance IS NOT NULL",
    )
    .fetch_one(pool)
    .await?;

    if food_count < 3 || nutrient_rows < 22 {
        bail!("fixture is incomplete: foods={food_count}, nutrient_rows={nutrient_rows}");
    }
    if state_counts.get("missing").copied().unwrap_or(0) < 1 {
        bail!("fixture does not demonstrate a missing nutrient value");
    }
    if logical_zero_count < 1 {
        bail!("fixture does not demonstrate a logical zero");
    }
    if source_provenance_count < 22 {
        bail!("fixture does not preserve source provenance for every nutrient observation");
    }

    println!(
        "schema verified: foods={food_count} nutrient_rows={nutrient_rows} \
         missing={} logical_zero={logical_zero_count} provenance={source_provenance_count}",
        state_counts.get("missing").copied().unwrap_or(0)
    );
    Ok(())
}

async fn catalog_table_count(pool: &PgPool) -> Result<i64> {
    sqlx::query_scalar(
        "SELECT count(*) FROM information_schema.tables \
         WHERE table_schema = 'public' \
         AND table_name IN ( \
             'foods', 'food_sources', 'food_source_links', 'nutrient_values' \
         )",
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
