# Perl AST to Neo4j

This project parses Perl source files, extracts ASTs (Abstract Syntax Trees), analyzes cross-file function calls and dependencies, and stores the resulting data in a Neo4j graph database for visualization or querying.

---

## 🧩 Components

### 1. `perform_perl_parser.py`
- Parses `.pl`, `.pm`, and `.perl` files
- Extracts packages, methods, use-statements, and script-level code
- Detects:
  - Intra-file and cross-file function calls
  - Package/module dependencies
- Outputs:
  - Individual AST files (optional)
  - Combined `combined_project_ast.json`
  - `project_summary.json` (metrics, dependencies, call stats)

### 2. `neo4j_writer.py`
- Connects to Neo4j and clears the DB
- Transforms the combined AST into nodes and relationships
- Stores:
  - FILE → PACKAGE → METHOD/SCRIPT hierarchy
  - USE_STATEMENTS
  - CROSS-FILE CALL relationships
  - Creates indexes and performs query tests

---

## 🚀 Getting Started

### Prerequisites
- Python 3.8+
- [Neo4j Desktop or Neo4j Aura](https://neo4j.com/download/)
- Perl files to analyze

### Setup
```bash
# Clone this repo and navigate into it
git clone <your-repo-url>
cd perl_ast_to_neo4j

# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt
