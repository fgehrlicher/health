use std::{
    collections::{BTreeMap, BTreeSet},
    env,
    fs::File,
    io::{Read, Write},
    path::{Path, PathBuf},
    process::ExitCode,
    str::FromStr,
    time::{SystemTime, UNIX_EPOCH},
};

use anyhow::{Context, Result, bail};
use calamine::{Data, Reader, open_workbook_auto};
use rust_decimal::Decimal;
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use sqlx::{PgPool, Row, postgres::PgPoolOptions};

const SOURCE_NAME: &str = "BLS 4.0";
const WORKBOOK_SHA256: &str = "524bbefe25b691f5cb3de7a9f3e27fa2967aebfeabf217d99414ba7806e78c60";
const DEFAULT_DATABASE_URL: &str = "postgres://health:health@127.0.0.1:5432/health";

struct Options {
    workbook: PathBuf,
    codes: PathBuf,
    dry_run: bool,
}

struct Columns {
    code: usize,
    german_name: usize,
    english_name: usize,
    energy: usize,
    protein: usize,
    fat: usize,
    carbs: usize,
    fiber: usize,
    oligosaccharides: usize,
    alcohol: usize,
    organic_acids: usize,
    polyols: usize,
}

#[derive(Debug)]
struct Food {
    code: String,
    german_name: String,
    english_name: String,
    energy: Decimal,
    protein: Option<Decimal>,
    fat: Option<Decimal>,
    carbs: Option<Decimal>,
    fiber: Option<Decimal>,
}

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
    let args: Vec<String> = env::args().skip(1).collect();
    if args.is_empty() || matches!(args[0].as_str(), "help" | "--help" | "-h") {
        print_help();
        return Ok(());
    }
    let options = parse_args(&args)?;
    let workbook_hash = sha256_file(&options.workbook)?;
    if workbook_hash != WORKBOOK_SHA256 {
        bail!("unexpected BLS workbook checksum: {workbook_hash}; expected {WORKBOOK_SHA256}");
    }

    let code_bytes = std::fs::read(&options.codes).context("read selected BLS codes")?;
    let codes_hash = hex_digest(&Sha256::digest(&code_bytes));
    let codes = parse_codes(std::str::from_utf8(&code_bytes).context("codes file is not UTF-8")?)?;
    let (foods, issues, corrected_energy) = read_workbook(&options.workbook, &codes)?;

    let (created, updated, skipped) = if options.dry_run {
        (0, 0, 0)
    } else {
        let database_url = env::var("DATABASE_URL").unwrap_or_else(|_| DEFAULT_DATABASE_URL.into());
        let pool = PgPoolOptions::new()
            .max_connections(5)
            .connect(&database_url)
            .await
            .context("connect to PostgreSQL using DATABASE_URL")?;
        write_foods(&pool, &foods).await?
    };

    let run_unix_seconds = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .context("read system time")?
        .as_secs();
    let report = json!({
        "source": SOURCE_NAME,
        "publisher": "Max Rubner-Institut",
        "citation": "Max Rubner-Institut (2025): Bundeslebensmittelschlüssel (BLS), Version 4.0 — Deutsche Nährstoffdatenbank. Karlsruhe. DOI: 10.25826/Data20251217-134202-0",
        "license": "CC BY 4.0",
        "download_url": "https://blsdb.de/download",
        "workbook_sha256": workbook_hash,
        "codes_sha256": codes_hash,
        "run_unix_seconds": run_unix_seconds,
        "dry_run": options.dry_run,
        "selected": foods.len(),
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "energy_corrected": corrected_energy,
        "nonnumeric_values": issues,
    });
    println!("{}", serde_json::to_string_pretty(&report)?);
    Ok(())
}

fn parse_args(args: &[String]) -> Result<Options> {
    if args.first().map(String::as_str) != Some("bls4") {
        bail!("expected `bls4`; run health-import --help");
    }
    let mut workbook = None;
    let mut codes = None;
    let mut dry_run = false;
    let mut index = 1;
    while index < args.len() {
        match args[index].as_str() {
            "--workbook" => {
                index += 1;
                workbook = Some(PathBuf::from(
                    args.get(index).context("--workbook needs a path")?,
                ));
            }
            "--codes" => {
                index += 1;
                codes = Some(PathBuf::from(
                    args.get(index).context("--codes needs a path")?,
                ));
            }
            "--dry-run" => dry_run = true,
            unknown => bail!("unknown argument {unknown:?}; run health-import --help"),
        }
        index += 1;
    }
    Ok(Options {
        workbook: workbook.context("--workbook is required")?,
        codes: codes.context("--codes is required")?,
        dry_run,
    })
}

fn sha256_file(path: &Path) -> Result<String> {
    let mut file = File::open(path).with_context(|| format!("open {}", path.display()))?;
    let mut hash = Sha256::new();
    let mut buffer = [0_u8; 64 * 1024];
    loop {
        let count = file.read(&mut buffer).context("read workbook")?;
        if count == 0 {
            break;
        }
        hash.update(&buffer[..count]);
    }
    Ok(hex_digest(&hash.finalize()))
}

fn hex_digest(bytes: &[u8]) -> String {
    bytes.iter().map(|byte| format!("{byte:02x}")).collect()
}

fn parse_codes(input: &str) -> Result<BTreeSet<String>> {
    let mut codes = BTreeSet::new();
    for (line_number, line) in input.lines().enumerate() {
        let code = line.trim();
        if code.is_empty() || code.starts_with('#') {
            continue;
        }
        if code.len() != 7
            || !code
                .chars()
                .all(|c| c.is_ascii_uppercase() || c.is_ascii_digit())
        {
            bail!("invalid BLS code {code:?} at line {}", line_number + 1);
        }
        if !codes.insert(code.to_owned()) {
            bail!("duplicate BLS code {code} at line {}", line_number + 1);
        }
    }
    if codes.is_empty() {
        bail!("codes file does not select any foods");
    }
    Ok(codes)
}

fn read_workbook(
    path: &Path,
    selected: &BTreeSet<String>,
) -> Result<(Vec<Food>, Vec<Value>, usize)> {
    let mut workbook = open_workbook_auto(path).context("open BLS workbook")?;
    let range = workbook
        .worksheet_range_at(0)
        .context("BLS workbook has no worksheet")?
        .context("read BLS worksheet")?;
    let mut rows = range.rows();
    let headers = rows.next().context("BLS worksheet is empty")?;
    let columns = Columns::from_headers(headers)?;
    let mut found = BTreeMap::new();
    let mut issues = Vec::new();
    let mut corrected_energy = 0;

    for (offset, row) in rows.enumerate() {
        let code = cell_text(row, columns.code)?;
        if !selected.contains(&code) {
            continue;
        }
        if found.contains_key(&code) {
            bail!("duplicate selected BLS code {code} in worksheet");
        }
        let food = parse_food(row, &columns, &code, &mut issues, &mut corrected_energy)
            .with_context(|| format!("BLS row {} ({code})", offset + 2))?;
        found.insert(code, food);
    }
    let found_codes: BTreeSet<_> = found.keys().cloned().collect();
    let missing: Vec<_> = selected.difference(&found_codes).collect();
    if !missing.is_empty() {
        bail!("selected BLS codes not found in workbook: {missing:?}");
    }
    Ok((found.into_values().collect(), issues, corrected_energy))
}

impl Columns {
    fn from_headers(row: &[Data]) -> Result<Self> {
        Ok(Self {
            code: find_header(row, "BLS Code", None)?,
            german_name: find_header(row, "Lebensmittelbezeichnung", None)?,
            english_name: find_header(row, "Food name", None)?,
            energy: find_header(row, "ENERCC ", Some("[kcal/100g]"))?,
            protein: find_header(row, "PROT625 ", Some("[g/100g]"))?,
            fat: find_header(row, "FAT ", Some("[g/100g]"))?,
            carbs: find_header(row, "CHO ", Some("[g/100g]"))?,
            fiber: find_header(row, "FIBT ", Some("[g/100g]"))?,
            oligosaccharides: find_header(row, "OLSAC ", Some("[g/100g]"))?,
            alcohol: find_header(row, "ALC ", Some("[g/100g]"))?,
            organic_acids: find_header(row, "OA ", Some("[g/100g]"))?,
            polyols: find_header(row, "POLYL ", Some("[g/100g]"))?,
        })
    }
}

fn find_header(row: &[Data], name: &str, unit: Option<&str>) -> Result<usize> {
    let matches: Vec<_> = row
        .iter()
        .enumerate()
        .filter(|(_, cell)| match cell {
            Data::String(text) => match unit {
                Some(unit) => text.starts_with(name) && text.contains(unit),
                None => text == name,
            },
            _ => false,
        })
        .map(|(index, _)| index)
        .collect();
    match matches.as_slice() {
        [index] => Ok(*index),
        [] => bail!("missing BLS column {name:?} with unit {unit:?}"),
        _ => bail!("ambiguous BLS column {name:?}"),
    }
}

fn cell_text(row: &[Data], column: usize) -> Result<String> {
    match row.get(column).unwrap_or(&Data::Empty) {
        Data::String(text) if !text.trim().is_empty() => Ok(text.trim().to_owned()),
        other => bail!("expected nonempty text, found {other:?}"),
    }
}

fn parse_food(
    row: &[Data],
    columns: &Columns,
    code: &str,
    issues: &mut Vec<Value>,
    corrected_energy: &mut usize,
) -> Result<Food> {
    let german_name = cell_text(row, columns.german_name)?;
    let english_name = cell_text(row, columns.english_name)?;
    let mut energy = parse_amount(row, columns.energy, code, "ENERCC", issues)?
        .context("energy must be numeric")?;
    let protein = parse_amount(row, columns.protein, code, "PROT625", issues)?;
    let fat = parse_amount(row, columns.fat, code, "FAT", issues)?;
    let carbs = parse_amount(row, columns.carbs, code, "CHO", issues)?;
    let fiber = parse_amount(row, columns.fiber, code, "FIBT", issues)?;
    let oligosaccharides = parse_amount(row, columns.oligosaccharides, code, "OLSAC", issues)?;

    for (name, amount) in [
        ("PROT625", protein),
        ("FAT", fat),
        ("CHO", carbs),
        ("FIBT", fiber),
        ("OLSAC", oligosaccharides),
    ] {
        if amount.is_some_and(|value| value > Decimal::ONE_HUNDRED) {
            bail!("{name} exceeds 100 g per 100 g");
        }
    }
    if energy > Decimal::from(1000) {
        bail!("ENERCC exceeds 1000 kcal per 100 g");
    }
    if oligosaccharides.is_some_and(|value| !value.is_zero()) {
        // BLS 4.0 erratum: published ENERCC counted OLSAC twice. Recompute from
        // the documented corrected formula; subtracting from rounded kcal can
        // disagree by 1 kcal with the result of the full calculation.
        let protein = protein.context("protein is needed for corrected energy")?;
        let fat = fat.context("fat is needed for corrected energy")?;
        let carbs = carbs.context("carbs are needed for corrected energy")?;
        let fiber = fiber.context("fiber is needed for corrected energy")?;
        let alcohol = parse_amount(row, columns.alcohol, code, "ALC", issues)?
            .context("alcohol is needed for corrected energy")?;
        let organic_acids = parse_amount(row, columns.organic_acids, code, "OA", issues)?
            .context("organic acids are needed for corrected energy")?;
        let polyols = parse_amount(row, columns.polyols, code, "POLYL", issues)?
            .context("polyols are needed for corrected energy")?;
        if [alcohol, organic_acids, polyols]
            .into_iter()
            .any(|value| value > Decimal::ONE_HUNDRED)
        {
            bail!("corrected-energy component exceeds 100 g per 100 g");
        }
        energy = (protein * Decimal::from(4)
            + fat * Decimal::from(9)
            + (carbs - polyols) * Decimal::from(4)
            + fiber * Decimal::TWO
            + alcohol * Decimal::from(7)
            + organic_acids * Decimal::from(3)
            + polyols * Decimal::new(24, 1))
        .round_dp(0);
        if energy.is_sign_negative() || energy > Decimal::from(1000) {
            bail!("corrected ENERCC is outside 0–1000 kcal per 100 g");
        }
        *corrected_energy += 1;
    }
    Ok(Food {
        code: code.to_owned(),
        german_name,
        english_name,
        energy,
        protein,
        fat,
        carbs,
        fiber,
    })
}

fn parse_amount(
    row: &[Data],
    column: usize,
    code: &str,
    field: &str,
    issues: &mut Vec<Value>,
) -> Result<Option<Decimal>> {
    let cell = row.get(column).unwrap_or(&Data::Empty);
    let numeric = match cell {
        Data::Float(value) if value.is_finite() => Some(value.to_string()),
        Data::Int(value) => Some(value.to_string()),
        Data::String(value) => {
            let value = value.trim();
            if value.is_empty() || matches!(value, "TR" | "<LOD" | "<LOQ" | "<LOD or <LOQ" | "-") {
                let marker = if value.is_empty() { "blank" } else { value };
                issues.push(json!({"code": code, "field": field, "marker": marker}));
                None
            } else {
                Some(value.to_owned())
            }
        }
        Data::Empty => {
            issues.push(json!({"code": code, "field": field, "marker": "blank"}));
            None
        }
        other => bail!("unsupported cell for {field}: {other:?}"),
    };
    let Some(numeric) = numeric else {
        return Ok(None);
    };
    let value = Decimal::from_str(&numeric)
        .or_else(|_| Decimal::from_scientific(&numeric))
        .with_context(|| format!("invalid {field} value {numeric:?}"))?;
    if value.is_sign_negative() {
        bail!("negative {field} value {numeric}");
    }
    Ok(Some(value))
}

async fn write_foods(pool: &PgPool, foods: &[Food]) -> Result<(usize, usize, usize)> {
    let mut transaction = pool.begin().await.context("start BLS import transaction")?;
    sqlx::query("SELECT pg_advisory_xact_lock(hashtext('health:bls4-import')::bigint)")
        .execute(&mut *transaction)
        .await?;
    let mut created = 0;
    let mut updated = 0;
    let mut skipped = 0;

    for food in foods {
        let existing = sqlx::query(
            "SELECT source.id, source.food_name, source.reference_quantity::text AS reference_quantity, \
                    source.reference_unit, source.energy_kcal::text AS energy_kcal, \
                    source.protein_g::text AS protein_g, source.fat_g::text AS fat_g, \
                    source.carbs_g::text AS carbs_g, source.fiber_g::text AS fiber_g, \
                    catalog.kind \
             FROM food_sources AS source JOIN foods AS catalog ON catalog.id = source.food_id \
             WHERE source.source_name = $1 AND source.external_id = $2",
        )
        .bind(SOURCE_NAME)
        .bind(&food.code)
        .fetch_all(&mut *transaction)
        .await?;
        if existing.len() > 1 {
            bail!("duplicate {SOURCE_NAME} source records for {}", food.code);
        }

        if let Some(existing) = existing.first() {
            let kind: String = existing.try_get("kind")?;
            if kind != "ingredient" {
                bail!("BLS source {} belongs to a non-ingredient food", food.code);
            }
            let unchanged = existing.try_get::<String, _>("food_name")? == food.german_name
                && existing.try_get::<String, _>("reference_quantity")? == "100"
                && existing.try_get::<String, _>("reference_unit")? == "g"
                && old_amount(existing, "energy_kcal")? == Some(food.energy)
                && old_amount(existing, "protein_g")? == food.protein
                && old_amount(existing, "fat_g")? == food.fat
                && old_amount(existing, "carbs_g")? == food.carbs
                && old_amount(existing, "fiber_g")? == food.fiber;
            if unchanged {
                skipped += 1;
                continue;
            }
            let id: i64 = existing.try_get("id")?;
            sqlx::query(
                "UPDATE food_sources SET food_name = $1, reference_quantity = 100, \
                    reference_unit = 'g', energy_kcal = $2::numeric, protein_g = $3::numeric, \
                    fat_g = $4::numeric, carbs_g = $5::numeric, fiber_g = $6::numeric \
                 WHERE id = $7",
            )
            .bind(&food.german_name)
            .bind(food.energy.to_string())
            .bind(food.protein.map(|value| value.to_string()))
            .bind(food.fat.map(|value| value.to_string()))
            .bind(food.carbs.map(|value| value.to_string()))
            .bind(food.fiber.map(|value| value.to_string()))
            .bind(id)
            .execute(&mut *transaction)
            .await?;
            updated += 1;
            continue;
        }

        let slug = format!("bls4-{}", food.code.to_ascii_lowercase());
        let conflict: Option<i64> = sqlx::query_scalar("SELECT id FROM foods WHERE slug = $1")
            .bind(&slug)
            .fetch_optional(&mut *transaction)
            .await?;
        if conflict.is_some() {
            bail!("food slug {slug} already exists without its BLS source");
        }
        let aliases: Vec<String> = if food.german_name == food.english_name {
            Vec::new()
        } else {
            vec![food.german_name.clone()]
        };
        let food_id: i64 = sqlx::query_scalar(
            "INSERT INTO foods (slug, name, aliases, kind) \
             VALUES ($1, $2, $3, 'ingredient') RETURNING id",
        )
        .bind(&slug)
        .bind(&food.english_name)
        .bind(&aliases)
        .fetch_one(&mut *transaction)
        .await?;
        sqlx::query(
            "INSERT INTO food_sources (food_id, source_name, external_id, food_name, \
                reference_quantity, reference_unit, energy_kcal, protein_g, fat_g, carbs_g, fiber_g) \
             VALUES ($1, $2, $3, $4, 100, 'g', $5::numeric, $6::numeric, $7::numeric, \
                $8::numeric, $9::numeric)",
        )
        .bind(food_id)
        .bind(SOURCE_NAME)
        .bind(&food.code)
        .bind(&food.german_name)
        .bind(food.energy.to_string())
        .bind(food.protein.map(|value| value.to_string()))
        .bind(food.fat.map(|value| value.to_string()))
        .bind(food.carbs.map(|value| value.to_string()))
        .bind(food.fiber.map(|value| value.to_string()))
        .execute(&mut *transaction)
        .await?;
        created += 1;
    }
    transaction.commit().await.context("commit BLS import")?;
    Ok((created, updated, skipped))
}

fn old_amount(row: &sqlx::postgres::PgRow, name: &str) -> Result<Option<Decimal>> {
    row.try_get::<Option<String>, _>(name)?
        .map(|value| Decimal::from_str(&value).context("parse stored numeric value"))
        .transpose()
}

fn print_help() {
    let _ = std::io::stdout().write_all(
        b"health-import bls4 --workbook PATH --codes PATH [--dry-run]\n\n\
          Imports only the explicitly selected BLS 4.0 codes. The workbook must match\n\
          the inspected official release checksum. --dry-run validates without a database.\n\
          Success prints a JSON import report. DATABASE_URL sets PostgreSQL.\n",
    );
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn codes_reject_duplicates_and_bad_ids() {
        assert!(parse_codes("F110100\nF110100\n").is_err());
        assert!(parse_codes("f110100\n").is_err());
        assert_eq!(parse_codes("# comment\nF110100\n\n").unwrap().len(), 1);
    }

    #[test]
    fn markers_are_null_not_zero() {
        let row = vec![Data::String("TR".into()), Data::Int(0)];
        let mut issues = Vec::new();
        assert_eq!(
            parse_amount(&row, 0, "F110100", "FIBT", &mut issues).unwrap(),
            None
        );
        assert_eq!(
            parse_amount(&row, 1, "F110100", "FAT", &mut issues).unwrap(),
            Some(Decimal::ZERO)
        );
        assert_eq!(issues.len(), 1);
    }

    #[test]
    fn rejects_negative_and_unknown_amounts() {
        let mut issues = Vec::new();
        assert!(parse_amount(&[Data::Int(-1)], 0, "F110100", "FAT", &mut issues).is_err());
        assert!(
            parse_amount(
                &[Data::String("mystery".into())],
                0,
                "F110100",
                "FAT",
                &mut issues
            )
            .is_err()
        );
    }

    #[test]
    fn corrects_published_energy_for_oligosaccharides() {
        let columns = Columns {
            code: 0,
            german_name: 1,
            english_name: 2,
            energy: 3,
            protein: 4,
            fat: 5,
            carbs: 6,
            fiber: 7,
            oligosaccharides: 8,
            alcohol: 9,
            organic_acids: 10,
            polyols: 11,
        };
        let row = vec![
            Data::String("G650132".into()),
            Data::String("Schwarzwurzel gekocht".into()),
            Data::String("Black salsify boiled".into()),
            Data::Int(51),
            Data::Float(1.3),
            Data::Float(0.4),
            Data::Float(6.6),
            Data::Int(5),
            Data::Float(2.539),
            Data::Int(0),
            Data::Float(0.25),
            Data::Float(0.066),
        ];
        let mut issues = Vec::new();
        let mut corrected = 0;
        let food = parse_food(&row, &columns, "G650132", &mut issues, &mut corrected).unwrap();
        assert_eq!(food.energy, Decimal::from(46));
        assert_eq!(corrected, 1);
    }

    #[test]
    fn recomputes_instead_of_subtracting_from_rounded_kcal() {
        let columns = Columns {
            code: 0,
            german_name: 1,
            english_name: 2,
            energy: 3,
            protein: 4,
            fat: 5,
            carbs: 6,
            fiber: 7,
            oligosaccharides: 8,
            alcohol: 9,
            organic_acids: 10,
            polyols: 11,
        };
        let row = vec![
            Data::String("S361000".into()),
            Data::String("Fruchtgummi".into()),
            Data::String("Fruit gummy".into()),
            Data::Int(312),
            Data::Float(4.8),
            Data::Float(0.3),
            Data::Float(70.7),
            Data::Float(1.01),
            Data::Float(2.4),
            Data::Int(0),
            Data::Float(0.271),
            Data::Float(0.019),
        ];
        let food = parse_food(&row, &columns, "S361000", &mut Vec::new(), &mut 0).unwrap();
        assert_eq!(food.energy, Decimal::from(308));
    }
}
