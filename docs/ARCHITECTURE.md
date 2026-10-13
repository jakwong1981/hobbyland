<!-- docs/ARCHITECTURE.md -->
# Architecture & Flow Diagrams

## 1. End-to-End Sequence — Dashboard

```mermaid
sequenceDiagram
    participant U as Browser (React)
    participant C as ProductController
    participant S as ComparisonService
    participant R as ProductRepository
    participant D as SQLite (node:sqlite)

    U->>C: GET /api/comparisons?grade=hg&q=...
    C->>C: zod validate query (400 on invalid)
    C->>R: findProducts({grade, q})
    R->>D: SELECT products JOIN shops
    D-->>R: rows
    R-->>C: ProductRow[]
    C->>S: buildComparisons(products)
    S-->>C: ComparisonRow[] (grouped, cheapestShop, saving)
    C-->>U: ApiResponse<ComparisonRow[]>
    U->>U: render table + CheaperBadge
```

## 2. End-to-End Sequence — CSV Import

```mermaid
sequenceDiagram
    participant J as Cron / CLI / Upload UI
    participant I as ImportService
    participant R as ProductRepository
    participant D as SQLite

    J->>I: CSV content (shop, grade)
    I->>I: parse + validate rows (skip invalid)
    I->>R: runInTransaction
    R->>D: INSERT import_batches
    loop each valid row
        R->>D: UPSERT products ON CONFLICT(shop_id, sku, grade)
    end
    R-->>I: commit (rollback on error)
    I-->>J: { batchId, rowCount, skipped }
```

## 3. Component / Class Hierarchy

```mermaid
classDiagram
    class App {
        +createApp(db) Express
    }
    class ProductController {
        +getComparisons()
        +getProducts()
        +getImports()
    }
    class ImportController {
        +postImport()
    }
    class ComparisonService {
        +buildComparisons(products) ComparisonRow[]
    }
    class ImportService {
        +parseProductCsv(content)
        +importProducts(repo, shop, grade, ...)
    }
    class ProductRepository {
        +findProducts(filters)
        +upsertProduct(...)
        +createBatch(...)
        +listBatches(limit)
        +runInTransaction(work)
    }
    class ImportCli

    App --> ProductController
    App --> ImportController
    ProductController --> ComparisonService
    ProductController --> ProductRepository
    ImportController --> ImportService
    ImportCli --> ImportService
    ImportService --> ProductRepository
    ProductRepository --> "node:sqlite" DatabaseSync
```

### Frontend component hierarchy

```mermaid
graph TD
    App --> FactionWipe
    App --> FactionCrest
    App --> FactionToggle
    App --> DashboardPage
    App --> ImportPage
    DashboardPage --> HeroBanner
    DashboardPage --> KitShowcase
    DashboardPage --> GradeTabs
    DashboardPage --> ShopFilter
    DashboardPage --> SearchBar
    DashboardPage --> ViewToggle
    DashboardPage --> FreshnessBar
    DashboardPage --> ComparisonTable
    DashboardPage --> ComparisonGallery
    HeroBanner --> MobileSuitArt
    HeroBanner --> StatTile
    StatTile --> useCountUp
    useCountUp --> usePrefersReducedMotion
    HeroBanner -.-> summarizeComparisons
    KitShowcase -.-> selectShowcaseKits
    KitShowcase --> ShopLogo
    GradeTabs --> GradeEmblem
    FreshnessBar --> ShopLogo
    ComparisonTable --> ProductImage
    ComparisonTable --> CheaperBadge
    ComparisonTable --> ShopLogo
    ComparisonGallery --> ProductImage
    ComparisonGallery --> CheaperBadge
    ComparisonGallery --> GradeEmblem
    CheaperBadge --> ShopLogo
    ProductImage -.-> productImageUrl
    selectShowcaseKits -.-> productImageUrl
```

### Dashboard view state

```mermaid
stateDiagram-v2
    [*] --> Table
    Table --> Gallery: 圖鑑
    Gallery --> Table: 表格
    state Table {
        [*] --> Unsorted
        Unsorted --> Asc: click header
        Asc --> Desc: click same header
        Desc --> Asc: click same header
    }
```

## 4. Data Model

```mermaid
erDiagram
    shops ||--o{ products : sells
    import_batches ||--o{ products : "imported in"
    shops {
        int id PK
        text code UK "hobbyland | animes-pro"
        text name
    }
    import_batches {
        int id PK
        text source_file
        text shop_code
        text grade
        int row_count
        int skipped_count
        text imported_at
    }
    products {
        int id PK
        int shop_id FK
        text sku "JAN-13"
        text grade "hg|mg|rg"
        text title
        real price
        real regular_price
        text url
        text stock
        text sell_type
        text image_url
        int batch_id FK
        text imported_at
    }
```

`UNIQUE (shop_id, sku, grade)` is the upsert key; indexes on `sku` and `grade` back the
comparison query.

## 5. Deployment Topology

```mermaid
flowchart LR
    subgraph Host
        CRON[cron job] --> SCR[hobbyland_scraper.py]
        SCR --> CSV[(9 CSV files)]
        CSV --> CLI[pnpm import:csv]
        subgraph Docker container :8080
            BE[Express backend<br/>node:24-slim] --> DB[(SQLite /data volume)]
            BE --> FE[frontend/dist static]
        end
        CLI --> DB
    end
    Browser -->|HTTP :8080| BE
```
