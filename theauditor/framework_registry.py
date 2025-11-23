"""Registry of framework detection patterns and test framework configurations."""

# Framework detection registry - defines where to find each framework
FRAMEWORK_REGISTRY = {
    # Python frameworks
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
    
    # JavaScript/TypeScript frameworks
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

    # Validation/Schema libraries (JavaScript/TypeScript)
    # These are sanitizers that reduce false positives in taint analysis
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
        "package_pattern": "joi",  # Matches both 'joi' and '@hapi/joi'
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

    # PHP frameworks
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
    
    # Go frameworks
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
    
    # Java frameworks
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
    
    # Rust frameworks
    "actix-web": {
        "language": "rust",
        "detection_sources": {
            "Cargo.toml": [
                ["dependencies"],
                ["dev-dependencies"],
                ["workspace", "dependencies"],
            ],
        },
        "package_pattern": "actix-web",
        "import_patterns": ["use actix_web", "actix_web::", "HttpServer"],
    },
    "rocket": {
        "language": "rust",
        "detection_sources": {
            "Cargo.toml": [
                ["dependencies"],
                ["dev-dependencies"],
                ["workspace", "dependencies"],
            ],
        },
        "package_pattern": "rocket",
        "import_patterns": ["use rocket", "rocket::", "#[launch]", "#[get(", "#[post("],
    },
    "axum": {
        "language": "rust",
        "detection_sources": {
            "Cargo.toml": [
                ["dependencies"],
                ["dev-dependencies"],
                ["workspace", "dependencies"],
            ],
        },
        "package_pattern": "axum",
        "import_patterns": ["use axum", "axum::", "Router::new"],
    },
    "warp": {
        "language": "rust",
        "detection_sources": {
            "Cargo.toml": [
                ["dependencies"],
                ["dev-dependencies"],
                ["workspace", "dependencies"],
            ],
        },
        "package_pattern": "warp",
        "import_patterns": ["use warp", "warp::", "warp::Filter"],
    },
    "tokio": {
        "language": "rust",
        "detection_sources": {
            "Cargo.toml": [
                ["dependencies"],
                ["dev-dependencies"],
                ["workspace", "dependencies"],
            ],
        },
        "package_pattern": "tokio",
        "import_patterns": ["use tokio", "tokio::", "#[tokio::main]"],
    },
    "async-std": {
        "language": "rust",
        "detection_sources": {
            "Cargo.toml": [
                ["dependencies"],
                ["dev-dependencies"],
                ["workspace", "dependencies"],
            ],
        },
        "package_pattern": "async-std",
        "import_patterns": ["use async_std", "async_std::"],
    },
    "diesel": {
        "language": "rust",
        "detection_sources": {
            "Cargo.toml": [
                ["dependencies"],
                ["dev-dependencies"],
                ["workspace", "dependencies"],
            ],
        },
        "package_pattern": "diesel",
        "import_patterns": ["use diesel", "diesel::", "diesel::prelude::*"],
        "file_markers": ["diesel.toml"],
    },
    "sqlx": {
        "language": "rust",
        "detection_sources": {
            "Cargo.toml": [
                ["dependencies"],
                ["dev-dependencies"],
                ["workspace", "dependencies"],
            ],
        },
        "package_pattern": "sqlx",
        "import_patterns": ["use sqlx", "sqlx::", "sqlx::query"],
    },
    "sea-orm": {
        "language": "rust",
        "detection_sources": {
            "Cargo.toml": [
                ["dependencies"],
                ["dev-dependencies"],
                ["workspace", "dependencies"],
            ],
        },
        "package_pattern": "sea-orm",
        "import_patterns": ["use sea_orm", "sea_orm::"],
    },
    "serde": {
        "language": "rust",
        "detection_sources": {
            "Cargo.toml": [
                ["dependencies"],
                ["dev-dependencies"],
                ["workspace", "dependencies"],
            ],
        },
        "package_pattern": "serde",
        "import_patterns": ["use serde", "serde::", "#[derive(Serialize", "#[derive(Deserialize"],
    },

    # Ruby frameworks
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
}


# Test framework detection registry
TEST_FRAMEWORK_REGISTRY = {
    "pytest": {
        "language": "python",
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
        "command": "python -m unittest discover -q",
        "import_patterns": ["import unittest", "from unittest"],
        "file_patterns": ["test*.py", "*_test.py"],
    },
    "jest": {
        "language": "javascript",
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
        "command": "npm test --silent",
        "detection_sources": {
            "package.json": [
                ["dependencies"],
                ["devDependencies"],
            ],
        },
        "config_files": ["vitest.config.js", "vitest.config.ts", "vite.config.js", "vite.config.ts"],
        "script_patterns": ["vitest"],
    },
    "mocha": {
        "language": "javascript",
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
    "go": {
        "language": "go",
        "command": "go test ./...",
        "file_patterns": ["*_test.go"],
        "detection_sources": {
            "go.mod": "exists",
        },
    },
    "junit": {
        "language": "java",
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
        "command": "rspec",
        "detection_sources": {
            "Gemfile": "line_search",
            "Gemfile.lock": "content_search",
        },
        "config_files": [".rspec", "spec/spec_helper.rb"],
        "directory_markers": ["spec/"],
    },
    "cargo": {
        "language": "rust",
        "command": "cargo test",
        "detection_sources": {
            "Cargo.toml": "exists",
        },
        "file_patterns": ["*_test.rs", "tests/*.rs"],
        "directory_markers": ["tests/"],
        "content_patterns": ["#[test]", "#[cfg(test)]"],
    },
}