fn main() {
    println!("cargo:rerun-if-changed=db/schema.sql");
    println!("cargo:rerun-if-changed=db/fixtures/development.sql");
}
