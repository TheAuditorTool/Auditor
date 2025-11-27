//! Actix-web Taint Test Fixture
//!
//! Source: web::Json, web::Query, web::Path (user input)
//! Sink: Command::new(), std::process::Command (command execution)
//!
//! Expected: Taint flow detected from web::* -> Command

use actix_web::{web, App, HttpResponse, HttpServer, Responder};
use serde::Deserialize;
use std::process::Command;

#[derive(Deserialize)]
struct ExecuteRequest {
    cmd: String,
}

#[derive(Deserialize)]
struct QueryParams {
    host: String,
}

#[derive(Deserialize)]
struct UserQuery {
    id: String,
}

// VULNERABLE: web::Json flows to Command::new
async fn execute_command(body: web::Json<ExecuteRequest>) -> impl Responder {
    let user_cmd = &body.cmd;
    let output = Command::new("sh")
        .arg("-c")
        .arg(user_cmd)  // SINK: Command injection
        .output()
        .expect("Failed to execute");
    HttpResponse::Ok().body(format!("{:?}", output))
}

// VULNERABLE: web::Query flows to Command
async fn ping_host(query: web::Query<QueryParams>) -> impl Responder {
    let host = &query.host;
    let output = Command::new("ping")
        .arg(host)  // SINK: Command injection
        .output()
        .expect("Failed to ping");
    HttpResponse::Ok().body(format!("{:?}", output))
}

// VULNERABLE: web::Path flows to SQL query string
async fn get_user(path: web::Path<String>) -> impl Responder {
    let user_id = path.into_inner();
    let query = format!("SELECT * FROM users WHERE id = {}", user_id);  // SINK: SQL injection
    HttpResponse::Ok().body(query)
}

// VULNERABLE: web::Query flows to format string (potential injection)
async fn search_users(query: web::Query<UserQuery>) -> impl Responder {
    let search_term = &query.id;
    let sql = format!("SELECT * FROM users WHERE name LIKE '%{}%'", search_term);  // SINK: SQL injection
    HttpResponse::Ok().body(sql)
}

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    HttpServer::new(|| {
        App::new()
            .route("/execute", web::post().to(execute_command))
            .route("/ping", web::get().to(ping_host))
            .route("/user/{id}", web::get().to(get_user))
            .route("/search", web::get().to(search_users))
    })
    .bind("127.0.0.1:8080")?
    .run()
    .await
}
