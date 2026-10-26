# Diagram patterns

Small starting points. Replace the example names with the user's terms.

## Contents

- Flowchart with a decision and a retry
- Swimlanes
- Service architecture
- Sequence with an error branch
- ER diagram
- State machine
- Gantt
- Graphviz dependency graph with clusters
- PlantUML sequence
- SVG fallback

## Flowchart with a decision and a retry

```mermaid
flowchart TD
  submit([Request submitted]) --> check{Complete?}
  check -- yes --> approve[Approve]
  check -- no --> ask[Ask for missing data]
  ask --> submit
  approve --> done([Closed])
```

## Swimlanes

```mermaid
flowchart LR
  subgraph requester[Requester]
    r1[Raise request]
  end
  subgraph team[Delivery team]
    t1[Triage] --> t2[Implement]
  end
  subgraph ops[Operations]
    o1[Deploy]
  end
  r1 --> t1
  t2 --> o1
```

## Service architecture

```mermaid
flowchart LR
  user([User]) --> web[Web client]
  web --> gw[API gateway]
  subgraph platform[Platform]
    gw --> svc[Order service]
    svc --> db[(Orders DB)]
    svc -. events .-> bus[[Event bus]]
  end
  bus --> report[Reporting]
```

## Sequence with an error branch

```mermaid
sequenceDiagram
  actor U as User
  participant A as App
  participant P as Payment API
  U->>A: Pay
  A->>P: Charge
  alt approved
    P-->>A: OK
    A-->>U: Receipt
  else declined
    P-->>A: Declined
    A-->>U: Try another card
  end
```

## ER diagram

```mermaid
erDiagram
  CUSTOMER ||--o{ ORDER : places
  ORDER ||--|{ ORDER_LINE : contains
  PRODUCT ||--o{ ORDER_LINE : "appears in"
```

## State machine

```mermaid
stateDiagram-v2
  [*] --> Draft
  Draft --> Review : submit
  Review --> Draft : changes requested
  Review --> Live : approved
  Live --> Retired : retire
  Retired --> [*]
```

## Gantt

```mermaid
gantt
  dateFormat YYYY-MM-DD
  title Release plan
  section Build
  Implement :a1, 2026-11-02, 10d
  Test      :a2, after a1, 5d
  section Ship
  Release   :milestone, after a2, 0d
```

## Graphviz dependency graph with clusters

```dot
digraph deps {
  rankdir=LR; nodesep=0.4; ranksep=0.7;
  node [shape=box, style=rounded];
  subgraph cluster_core { label="Core"; api; domain; }
  subgraph cluster_data { label="Data"; repo; db [shape=cylinder]; }
  api -> domain -> repo -> db;
}
```

## PlantUML sequence

```plantuml
@startuml
actor User
participant "App" as App
database "Store" as DB
User -> App : Save
App -> DB : Insert
DB --> App : OK
App --> User : Saved
@enduml
```

## SVG fallback

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="420" height="120" viewBox="0 0 420 120" role="img">
  <title>Two-step flow</title>
  <rect x="10" y="35" width="150" height="50" rx="8" fill="#ffffff" stroke="#333333"/>
  <text x="85" y="65" text-anchor="middle" font-family="sans-serif" font-size="14">Input</text>
  <line x1="160" y1="60" x2="250" y2="60" stroke="#333333" stroke-width="2"/>
  <polygon points="250,54 262,60 250,66" fill="#333333"/>
  <rect x="262" y="35" width="150" height="50" rx="8" fill="#ffffff" stroke="#333333"/>
  <text x="337" y="65" text-anchor="middle" font-family="sans-serif" font-size="14">Output</text>
</svg>
```
