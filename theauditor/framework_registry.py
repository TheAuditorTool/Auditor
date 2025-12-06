"""Registry of framework detection patterns and test framework configurations."""

FRAMEWORK_REGISTRY = {
    "django": {
        "language": "python",
        "detection_sources": {
            "pyproject.toml": [
                ["project", "dependencies"],
                ["tool", "poetry", "dependencies"],
                ["tool", "poetry", "group", "*", "dependencies"],
                ["tool", "pdm", "dependencies"],
                ["tool", "setuptools", "install_requires"],
                ["project", "optional-dependencies", "*"],
            ],
            "requirements.txt": "line_search",
            "requirements-dev.txt": "line_search",
            "setup.py": "content_search",
            "setup.cfg": ["options", "install_requires"],
        },
        "import_patterns": ["from django", "import django"],
        "file_markers": ["manage.py", "wsgi.py"],
    },
    "flask": {
        "language": "python",
        "detection_sources": {
            "pyproject.toml": [
                ["project", "dependencies"],
                ["tool", "poetry", "dependencies"],
                ["tool", "poetry", "group", "*", "dependencies"],
                ["tool", "pdm", "dependencies"],
                ["project", "optional-dependencies", "*"],
            ],
            "requirements.txt": "line_search",
            "requirements-dev.txt": "line_search",
            "setup.py": "content_search",
            "setup.cfg": ["options", "install_requires"],
        },
        "import_patterns": ["from flask", "import flask"],
    },
    "fastapi": {
        "language": "python",
        "detection_sources": {
            "pyproject.toml": [
                ["project", "dependencies"],
                ["tool", "poetry", "dependencies"],
                ["tool", "poetry", "group", "*", "dependencies"],
                ["tool", "pdm", "dependencies"],
                ["project", "optional-dependencies", "*"],
            ],
            "requirements.txt": "line_search",
            "requirements-dev.txt": "line_search",
            "setup.py": "content_search",
            "setup.cfg": ["options", "install_requires"],
        },
        "import_patterns": ["from fastapi", "import fastapi"],
    },
    "pyramid": {
        "language": "python",
        "detection_sources": {
            "pyproject.toml": [
                ["project", "dependencies"],
                ["tool", "poetry", "dependencies"],
                ["tool", "poetry", "group", "*", "dependencies"],
                ["tool", "pdm", "dependencies"],
                ["project", "optional-dependencies", "*"],
            ],
            "requirements.txt": "line_search",
            "requirements-dev.txt": "line_search",
            "setup.py": "content_search",
            "setup.cfg": ["options", "install_requires"],
        },
        "import_patterns": ["from pyramid", "import pyramid"],
    },
    "tornado": {
        "language": "python",
        "detection_sources": {
            "pyproject.toml": [
                ["project", "dependencies"],
                ["tool", "poetry", "dependencies"],
                ["tool", "poetry", "group", "*", "dependencies"],
                ["tool", "pdm", "dependencies"],
                ["project", "optional-dependencies", "*"],
            ],
            "requirements.txt": "line_search",
            "requirements-dev.txt": "line_search",
            "setup.py": "content_search",
            "setup.cfg": ["options", "install_requires"],
        },
        "import_patterns": ["from tornado", "import tornado"],
    },
    "bottle": {
        "language": "python",
        "detection_sources": {
            "pyproject.toml": [
                ["project", "dependencies"],
                ["tool", "poetry", "dependencies"],
                ["tool", "poetry", "group", "*", "dependencies"],
                ["tool", "pdm", "dependencies"],
                ["project", "optional-dependencies", "*"],
            ],
            "requirements.txt": "line_search",
            "requirements-dev.txt": "line_search",
            "setup.py": "content_search",
            "setup.cfg": ["options", "install_requires"],
        },
        "import_patterns": ["from bottle", "import bottle"],
    },
    "aiohttp": {
        "language": "python",
        "detection_sources": {
            "pyproject.toml": [
                ["project", "dependencies"],
                ["tool", "poetry", "dependencies"],
                ["tool", "poetry", "group", "*", "dependencies"],
                ["tool", "pdm", "dependencies"],
                ["project", "optional-dependencies", "*"],
            ],
            "requirements.txt": "line_search",
            "requirements-dev.txt": "line_search",
            "setup.py": "content_search",
            "setup.cfg": ["options", "install_requires"],
        },
        "import_patterns": ["from aiohttp", "import aiohttp"],
    },
    "sanic": {
        "language": "python",
        "detection_sources": {
            "pyproject.toml": [
                ["project", "dependencies"],
                ["tool", "poetry", "dependencies"],
                ["tool", "poetry", "group", "*", "dependencies"],
                ["tool", "pdm", "dependencies"],
                ["project", "optional-dependencies", "*"],
            ],
            "requirements.txt": "line_search",
            "requirements-dev.txt": "line_search",
            "setup.py": "content_search",
            "setup.cfg": ["options", "install_requires"],
        },
        "import_patterns": ["from sanic", "import sanic"],
    },
    "express": {
        "language": "javascript",
        "detection_sources": {
            "package.json": [
                ["dependencies"],
                ["devDependencies"],
            ],
        },
        "import_patterns": ["express", "require('express')", "from 'express'"],
    },
    "nestjs": {
        "language": "javascript",
        "detection_sources": {
            "package.json": [
                ["dependencies"],
                ["devDependencies"],
            ],
        },
        "package_pattern": "@nestjs/core",
        "import_patterns": ["@nestjs"],
    },
    "next": {
        "language": "javascript",
        "detection_sources": {
            "package.json": [
                ["dependencies"],
                ["devDependencies"],
            ],
        },
        "import_patterns": ["next/", "from 'next'"],
    },
    "react": {
        "language": "javascript",
        "detection_sources": {
            "package.json": [
                ["dependencies"],
                ["devDependencies"],
            ],
        },
        "import_patterns": ["react", "from 'react'", "React"],
    },
    "vue": {
        "language": "javascript",
        "detection_sources": {
            "package.json": [
                ["dependencies"],
                ["devDependencies"],
            ],
        },
        "import_patterns": ["vue", "from 'vue'"],
        "file_markers": ["*.vue"],
    },
    "angular": {
        "language": "javascript",
        "detection_sources": {
            "package.json": [
                ["dependencies"],
                ["devDependencies"],
            ],
        },
        "package_pattern": "@angular/core",
        "import_patterns": ["@angular"],
        "file_markers": ["angular.json"],
    },
    "fastify": {
        "language": "javascript",
        "detection_sources": {
            "package.json": [
                ["dependencies"],
                ["devDependencies"],
            ],
        },
        "import_patterns": ["fastify"],
    },
    "koa": {
        "language": "javascript",
        "detection_sources": {
            "package.json": [
                ["dependencies"],
                ["devDependencies"],
            ],
        },
        "import_patterns": ["koa", "require('koa')"],
    },
    "vite": {
        "language": "javascript",
        "detection_sources": {
            "package.json": [
                ["dependencies"],
                ["devDependencies"],
            ],
        },
        "import_patterns": ["vite"],
        "config_files": ["vite.config.js", "vite.config.ts"],
    },
    "zod": {
        "language": "javascript",
        "detection_sources": {
            "package.json": [
                ["dependencies"],
                ["devDependencies"],
            ],
        },
        "import_patterns": ["from 'zod'", "import { z }", "import * as z from 'zod'"],
        "category": "validation",
    },
    "joi": {
        "language": "javascript",
        "detection_sources": {
            "package.json": [
                ["dependencies"],
                ["devDependencies"],
            ],
        },
        "package_pattern": "joi",
        "import_patterns": ["require('joi')", "from 'joi'", "import Joi", "import * as Joi"],
        "category": "validation",
    },
    "yup": {
        "language": "javascript",
        "detection_sources": {
            "package.json": [
                ["dependencies"],
                ["devDependencies"],
            ],
        },
        "import_patterns": ["from 'yup'", "import * as yup", "import yup"],
        "category": "validation",
    },
    "ajv": {
        "language": "javascript",
        "detection_sources": {
            "package.json": [
                ["dependencies"],
                ["devDependencies"],
            ],
        },
        "import_patterns": ["require('ajv')", "from 'ajv'", "new Ajv", "import Ajv"],
        "category": "validation",
    },
    "class-validator": {
        "language": "javascript",
        "detection_sources": {
            "package.json": [
                ["dependencies"],
                ["devDependencies"],
            ],
        },
        "import_patterns": ["from 'class-validator'", "import { validate }"],
        "category": "validation",
    },
    "express-validator": {
        "language": "javascript",
        "detection_sources": {
            "package.json": [
                ["dependencies"],
                ["devDependencies"],
            ],
        },
        "import_patterns": ["from 'express-validator'", "require('express-validator')"],
        "category": "validation",
    },
    "laravel": {
        "language": "php",
        "detection_sources": {
            "composer.json": [
                ["require"],
                ["require-dev"],
            ],
        },
        "package_pattern": "laravel/framework",
        "file_markers": ["artisan", "bootstrap/app.php"],
    },
    "symfony": {
        "language": "php",
        "detection_sources": {
            "composer.json": [
                ["require"],
                ["require-dev"],
            ],
        },
        "package_pattern": "symfony/framework-bundle",
        "file_markers": ["bin/console", "config/bundles.php"],
    },
    "slim": {
        "language": "php",
        "detection_sources": {
            "composer.json": [
                ["require"],
                ["require-dev"],
            ],
        },
        "package_pattern": "slim/slim",
    },
    "lumen": {
        "language": "php",
        "detection_sources": {
            "composer.json": [
                ["require"],
                ["require-dev"],
            ],
        },
        "package_pattern": "laravel/lumen-framework",
        "file_markers": ["artisan"],
    },
    "codeigniter": {
        "language": "php",
        "detection_sources": {
            "composer.json": [
                ["require"],
                ["require-dev"],
            ],
        },
        "package_pattern": "codeigniter4/framework",
        "file_markers": ["spark"],
    },
    "gin": {
        "language": "go",
        "detection_sources": {
            "go.mod": "content_search",
        },
        "package_pattern": "github.com/gin-gonic/gin",
        "import_patterns": ["github.com/gin-gonic/gin"],
    },
    "echo": {
        "language": "go",
        "detection_sources": {
            "go.mod": "content_search",
        },
        "package_pattern": "github.com/labstack/echo",
        "import_patterns": ["github.com/labstack/echo"],
    },
    "fiber": {
        "language": "go",
        "detection_sources": {
            "go.mod": "content_search",
        },
        "package_pattern": "github.com/gofiber/fiber",
        "import_patterns": ["github.com/gofiber/fiber"],
    },
    "beego": {
        "language": "go",
        "detection_sources": {
            "go.mod": "content_search",
        },
        "package_pattern": "github.com/beego/beego",
        "import_patterns": ["github.com/beego/beego"],
    },
    "chi": {
        "language": "go",
        "detection_sources": {
            "go.mod": "content_search",
        },
        "package_pattern": "github.com/go-chi/chi",
        "import_patterns": ["github.com/go-chi/chi"],
    },
    "gorilla": {
        "language": "go",
        "detection_sources": {
            "go.mod": "content_search",
        },
        "package_pattern": "github.com/gorilla/mux",
        "import_patterns": ["github.com/gorilla/mux"],
    },
    "net_http": {
        "language": "go",
        "detection_sources": {
            "go.mod": "exists",
        },
        "import_patterns": ["net/http"],
        "file_markers": ["*.go"],
    },
    "gorm": {
        "language": "go",
        "detection_sources": {
            "go.mod": "content_search",
        },
        "package_pattern": "gorm.io/gorm",
        "import_patterns": ["gorm.io/gorm", "gorm.io/driver"],
    },
    "sqlx_go": {
        "language": "go",
        "detection_sources": {
            "go.mod": "content_search",
        },
        "package_pattern": "github.com/jmoiron/sqlx",
        "import_patterns": ["github.com/jmoiron/sqlx"],
    },
    "ent": {
        "language": "go",
        "detection_sources": {
            "go.mod": "content_search",
        },
        "package_pattern": "entgo.io/ent",
        "import_patterns": ["entgo.io/ent"],
    },
    "cobra": {
        "language": "go",
        "detection_sources": {
            "go.mod": "content_search",
        },
        "package_pattern": "github.com/spf13/cobra",
        "import_patterns": ["github.com/spf13/cobra"],
    },
    "grpc_go": {
        "language": "go",
        "detection_sources": {
            "go.mod": "content_search",
        },
        "package_pattern": "google.golang.org/grpc",
        "import_patterns": ["google.golang.org/grpc"],
    },
    "spring": {
        "language": "java",
        "detection_sources": {
            "pom.xml": "content_search",
            "build.gradle": "content_search",
            "build.gradle.kts": "content_search",
        },
        "package_pattern": "spring",
        "content_patterns": ["spring-boot", "springframework"],
    },
    "micronaut": {
        "language": "java",
        "detection_sources": {
            "pom.xml": "content_search",
            "build.gradle": "content_search",
            "build.gradle.kts": "content_search",
        },
        "package_pattern": "io.micronaut",
        "content_patterns": ["io.micronaut"],
    },
    "quarkus": {
        "language": "java",
        "detection_sources": {
            "pom.xml": "content_search",
            "build.gradle": "content_search",
            "build.gradle.kts": "content_search",
        },
        "package_pattern": "io.quarkus",
        "content_patterns": ["io.quarkus"],
    },
    "dropwizard": {
        "language": "java",
        "detection_sources": {
            "pom.xml": "content_search",
            "build.gradle": "content_search",
            "build.gradle.kts": "content_search",
        },
        "package_pattern": "io.dropwizard",
        "content_patterns": ["io.dropwizard"],
    },
    "play": {
        "language": "java",
        "detection_sources": {
            "build.sbt": "content_search",
            "build.gradle": "content_search",
        },
        "package_pattern": "com.typesafe.play",
        "content_patterns": ["com.typesafe.play"],
    },
    # Rust web frameworks - detected via Cargo.toml and use statements
    "actix-web": {
        "language": "rust",
        "detection_sources": {"Cargo.toml": [["dependencies"], ["dev-dependencies"]]},
        "package_pattern": "actix-web",
        "import_patterns": ["actix_web::", "HttpServer::new", "web::resource"],
        "attribute_patterns": ["#[actix_web::main]", "#[get(", "#[post(", "#[route("],
    },
    "axum": {
        "language": "rust",
        "detection_sources": {"Cargo.toml": [["dependencies"], ["dev-dependencies"]]},
        "package_pattern": "axum",
        "import_patterns": ["axum::", "axum::Router", "axum::extract"],
        "attribute_patterns": ["#[debug_handler]"],
    },
    "rocket": {
        "language": "rust",
        "detection_sources": {"Cargo.toml": [["dependencies"], ["dev-dependencies"]]},
        "package_pattern": "rocket",
        "import_patterns": ["rocket::", "rocket::serde"],
        "attribute_patterns": ["#[launch]", "#[rocket::main]", "#[get(", "#[post("],
    },
    "warp": {
        "language": "rust",
        "detection_sources": {"Cargo.toml": [["dependencies"], ["dev-dependencies"]]},
        "package_pattern": "warp",
        "import_patterns": ["warp::", "warp::Filter", "warp::path"],
    },
    # Rust async runtimes
    "tokio": {
        "language": "rust",
        "detection_sources": {"Cargo.toml": [["dependencies"], ["dev-dependencies"]]},
        "package_pattern": "tokio",
        "import_patterns": ["tokio::", "tokio::spawn", "tokio::sync"],
        "attribute_patterns": ["#[tokio::main]", "#[tokio::test]"],
    },
    "async-std": {
        "language": "rust",
        "detection_sources": {"Cargo.toml": [["dependencies"], ["dev-dependencies"]]},
        "package_pattern": "async-std",
        "import_patterns": ["async_std::", "async_std::task"],
        "attribute_patterns": ["#[async_std::main]", "#[async_std::test]"],
    },
    # Rust ORMs and database libs
    "diesel": {
        "language": "rust",
        "detection_sources": {"Cargo.toml": [["dependencies"], ["dev-dependencies"]]},
        "package_pattern": "diesel",
        "import_patterns": ["diesel::", "diesel::prelude"],
        "file_markers": ["diesel.toml", "migrations/"],
        "attribute_patterns": ["#[derive(Queryable", "#[derive(Insertable", "#[table_name"],
    },
    "sqlx": {
        "language": "rust",
        "detection_sources": {"Cargo.toml": [["dependencies"], ["dev-dependencies"]]},
        "package_pattern": "sqlx",
        "import_patterns": ["sqlx::", "sqlx::query", "sqlx::FromRow"],
        "attribute_patterns": ["#[derive(sqlx::FromRow)", "#[sqlx("],
    },
    "sea-orm": {
        "language": "rust",
        "detection_sources": {"Cargo.toml": [["dependencies"], ["dev-dependencies"]]},
        "package_pattern": "sea-orm",
        "import_patterns": ["sea_orm::", "sea_orm::entity"],
        "attribute_patterns": ["#[derive(DeriveEntityModel"],
    },
    # Rust serialization
    "serde": {
        "language": "rust",
        "detection_sources": {"Cargo.toml": [["dependencies"], ["dev-dependencies"]]},
        "package_pattern": "serde",
        "import_patterns": ["serde::", "serde_json::"],
        "attribute_patterns": ["#[derive(Serialize", "#[derive(Deserialize", "#[serde("],
    },
    "validator": {
        "language": "rust",
        "category": "validation",
        "detection_sources": {"Cargo.toml": [["dependencies"], ["dev-dependencies"]]},
        "package_pattern": "validator",
        "import_patterns": ["validator::"],
        "attribute_patterns": ["#[derive(Validate)", "#[validate("],
    },
    "rails": {
        "language": "ruby",
        "detection_sources": {
            "Gemfile": "line_search",
            "Gemfile.lock": "content_search",
        },
        "package_pattern": "rails",
        "file_markers": ["Rakefile", "config.ru", "bin/rails"],
    },
    "sinatra": {
        "language": "ruby",
        "detection_sources": {
            "Gemfile": "line_search",
            "Gemfile.lock": "content_search",
        },
        "package_pattern": "sinatra",
    },
    "hanami": {
        "language": "ruby",
        "detection_sources": {
            "Gemfile": "line_search",
            "Gemfile.lock": "content_search",
        },
        "package_pattern": "hanami",
    },
    "grape": {
        "language": "ruby",
        "detection_sources": {
            "Gemfile": "line_search",
            "Gemfile.lock": "content_search",
        },
        "package_pattern": "grape",
    },
    "pytest": {
        "language": "python",
        "category": "test",
        "command": "pytest -q -p no:cacheprovider",
        "detection_sources": {
            "pyproject.toml": [
                ["project", "dependencies"],
                ["project", "optional-dependencies", "test"],
                ["project", "optional-dependencies", "dev"],
                ["project", "optional-dependencies", "tests"],
                ["tool", "poetry", "dependencies"],
                ["tool", "poetry", "group", "dev", "dependencies"],
                ["tool", "poetry", "group", "test", "dependencies"],
                ["tool", "poetry", "dev-dependencies"],
                ["tool", "pdm", "dev-dependencies"],
                ["tool", "hatch", "envs", "default", "dependencies"],
            ],
            "requirements.txt": "line_search",
            "requirements-dev.txt": "line_search",
            "requirements-test.txt": "line_search",
            "setup.cfg": ["options", "tests_require"],
            "setup.py": "content_search",
            "tox.ini": "content_search",
        },
        "config_files": ["pytest.ini", ".pytest.ini", "pyproject.toml"],
        "config_sections": {
            "pyproject.toml": [
                ["tool", "pytest"],
                ["tool", "pytest", "ini_options"],
            ],
            "setup.cfg": [
                ["tool:pytest"],
                ["pytest"],
            ],
        },
    },
    "unittest": {
        "language": "python",
        "category": "test",
        "command": "python -m unittest discover -q",
        "import_patterns": ["import unittest", "from unittest"],
        "file_patterns": ["test*.py", "*_test.py"],
    },
    "jest": {
        "language": "javascript",
        "category": "test",
        "command": "npm test --silent",
        "detection_sources": {
            "package.json": [
                ["dependencies"],
                ["devDependencies"],
            ],
        },
        "config_files": ["jest.config.js", "jest.config.ts", "jest.config.json"],
        "config_sections": {
            "package.json": [["jest"]],
        },
        "script_patterns": ["jest"],
    },
    "vitest": {
        "language": "javascript",
        "category": "test",
        "command": "npm test --silent",
        "detection_sources": {
            "package.json": [
                ["dependencies"],
                ["devDependencies"],
            ],
        },
        "config_files": [
            "vitest.config.js",
            "vitest.config.ts",
            "vite.config.js",
            "vite.config.ts",
        ],
        "script_patterns": ["vitest"],
    },
    "mocha": {
        "language": "javascript",
        "category": "test",
        "command": "npm test --silent",
        "detection_sources": {
            "package.json": [
                ["dependencies"],
                ["devDependencies"],
            ],
        },
        "config_files": [".mocharc.js", ".mocharc.json", ".mocharc.yaml", ".mocharc.yml"],
        "script_patterns": ["mocha"],
    },
    "gotest": {
        "language": "go",
        "category": "test",
        "command": "go test ./...",
        "file_patterns": ["*_test.go"],
        "detection_sources": {
            "go.mod": "exists",
        },
    },
    "junit": {
        "language": "java",
        "category": "test",
        "command_maven": "mvn test",
        "command_gradle": "gradle test",
        "detection_sources": {
            "pom.xml": "content_search",
            "build.gradle": "content_search",
            "build.gradle.kts": "content_search",
        },
        "content_patterns": ["junit", "testImplementation"],
        "import_patterns": ["import org.junit"],
        "file_patterns": ["*Test.java", "Test*.java"],
    },
    "rspec": {
        "language": "ruby",
        "category": "test",
        "command": "rspec",
        "detection_sources": {
            "Gemfile": "line_search",
            "Gemfile.lock": "content_search",
        },
        "config_files": [".rspec", "spec/spec_helper.rb"],
        "directory_markers": ["spec/"],
    },
    "cargo-test": {
        "language": "rust",
        "category": "test",
        "command": "cargo test --quiet",
        "detection_sources": {"Cargo.toml": "exists"},
        "file_patterns": ["tests/*.rs", "src/**/*_test.rs"],
        "directory_markers": ["tests/", "benches/"],
        "attribute_patterns": ["#[test]", "#[cfg(test)]", "#[tokio::test]", "#[ignore]"],
    },
    "bash": {
        "language": "bash",
        "detection_sources": {},
        "file_markers": ["*.sh", "*.bash"],
        "shebang_patterns": ["#!/bin/bash", "#!/usr/bin/env bash", "#!/bin/sh"],
    },
    "shellcheck": {
        "language": "bash",
        "category": "lint",
        "command": "shellcheck",
        "file_patterns": ["*.sh", "*.bash"],
        "config_files": [".shellcheckrc"],
    },
    "bats": {
        "language": "bash",
        "category": "test",
        "command": "bats",
        "file_patterns": ["*.bats", "test/*.bats"],
        "directory_markers": ["test/"],
    },
}
