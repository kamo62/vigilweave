from app.services.language_detector import detect_languages


def test_detect_languages_covers_extended_matrix(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.go").write_text("package main\n", encoding="utf-8")
    (repo / "main.tf.json").write_text('{"resource":{}}\n', encoding="utf-8")
    (repo / "app.php").write_text("<?php echo 'ok';\n", encoding="utf-8")
    (repo / "service.rb").write_text("puts 'ok'\n", encoding="utf-8")
    (repo / "engine.rs").write_text("fn main() {}\n", encoding="utf-8")
    (repo / "App.swift").write_text("struct App {}\n", encoding="utf-8")
    (repo / "schema.pkb").write_text(
        "create or replace package body demo as end;\n",
        encoding="utf-8",
    )
    (repo / "stack.yaml").write_text(
        "AWSTemplateFormatVersion: '2010-09-09'\nResources: {}\n",
        encoding="utf-8",
    )
    (repo / "build.gradle.kts").write_text("plugins {}\n", encoding="utf-8")
    (repo / "Dockerfile").write_text("FROM alpine:3.22\n", encoding="utf-8")

    languages = detect_languages(repo)

    assert languages["go"] == 1
    assert languages["terraform"] == 1
    assert languages["php"] == 1
    assert languages["ruby"] == 1
    assert languages["rust"] == 1
    assert languages["swift"] == 1
    assert languages["plsql"] == 1
    assert languages["cloudformation"] == 1
    assert languages["kotlin"] == 1
    assert languages["dockerfile"] == 1
