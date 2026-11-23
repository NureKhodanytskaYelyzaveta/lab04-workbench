# Архітектура робочого місця

```
┌─────────────────────────── streamlit_app.py ───────────────────────────┐
│ Питання до бази знань │ Команда агентів │ Історія і метрики │ ІНТЕРФЕЙС
└───────────────┬───────────────────┬─────────────────────┬──────────────┘
                ▼                   ▼                     ▼
┌──────────────────────── workbench/service.py ──────────────────────────┐
│ ask()        run_team()        save_scene()      rate()     history    │ СЕРВІС
└───────┬──────────────┬─────────────────┬───────────────────┬───────────┘
        ▼              ▼                 ▼                   ▼
 app/kb_assistant   app/agent.py   workbench/exporters   workbench/storage  АДАПТЕРИ
 (ADK, ЛР 2)        (граф, ЛР 3)   (.md .json .yarn,     (SQLite)
                         │          нотатка в Inbox)
                         ▼                 ▼
   kb/ (Chroma) ◄── retrieve_context   Obsidian vault/Inbox               ЗОВНІШНІ
        │                                                                  СИСТЕМИ
        └──────── Gemini API (моделі агентів і ембедингів) ───────────────
```

## Граф команди (ЛР 3 + вузол контексту)

```
START → intake ──reject──► reject
          │ ok
          ▼
   retrieve_context   ← НОВИЙ вузол: kb_search(request) → state["kb_context"]
          ▼
   scene_designer ◄──── fix / revise ────────────────────────┐
          ▼                                                   │
     scene_check ── fix ──────────────────────────────────────┤
          │ ok  (паралельно)                                  │
   audio_designer   visual_designer                           │
          └──► plans (JoinNode) ◄──┘                          │
                    ▼                                         │
               link_check ── fix ─────────────────────────────┤
                    ▼                                         │
                director → gate ──revise──────────────────────┘
                              │ publish
                              ▼
                           publish → звіт
```

`retrieve_context` — функція, а не агент: запит до бази знань завжди один, окремий виклик
моделі для його формулювання не потрібен. Фрагменти потрапляють лише в інструкцію
`scene_designer` (як дані в тегах `<fragment>`, не як інструкції).
