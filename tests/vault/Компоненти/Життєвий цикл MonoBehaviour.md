---
tags: [компоненти, життєвий-цикл]
aliases: [MonoBehaviour lifecycle]
source: "Тестова нотатка (фікстура)"
updated: 2026-11-01
---
# Життєвий цикл MonoBehaviour

Тестова нотатка про порядок виклику подій скрипта.

## Порядок подій
Awake викликається першим, потім OnEnable, потім Start. Update виконується щокадру, див. [[Update і FixedUpdate]].

## Знищення
OnDisable і OnDestroy викликаються під час вимкнення та знищення об'єкта.
