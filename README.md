# Perl to Java Migration Tool

A comprehensive automated migration tool that converts Perl code to Java using AST parsing, Neo4j graph storage, and LLM-powered code generation.

## 🏗️ How It Works

```
Perl Code → perform_perl_parser.py → AST files → neo4j_writer.py → Neo4j → main.py (with agents) → Java Code
```

## 📁 Project Structure

```
perl_to_java_migration_tool/
├── perl parser/
│   ├── perform_perl_parser.py    # Parses Perl code and generates AST
│   ├── neo4j_writer.py          # Writes AST data to Neo4j database
│   ├── ast/                     # Generated AST files stored here
│   ├── output/                  # Parser output files
│   ├── examples/                # Example Perl files for testing
│   ├── requirements.txt         # Python dependencies
│   └── README.md
│
└── java agent/
    ├── main.py                  # Main execution file with all agents
    ├── config.py                # Configuration settings
    ├── state.py                 # State management
    ├── setup.py                 # Setup and initialization
    ├── agents/                  # LLM agents for code generation
    ├── prompts/                 # LLM prompts and templates
    ├── output/                  # Generated Java code output
    ├── requirements.txt         # Python dependencies
    └── README.md
```

## 🚀 How to Run

### Prerequisites
- Python 3.x
- Neo4j database instance running
- LLM API access (OpenAI or other providers)
- Required Python packages (see requirements.txt in each folder)

### Step 1: Install Dependencies
```bash
# Install Perl parser dependencies
cd "perl parser"
pip install -r requirements.txt

# Install Java agent dependencies  
cd "../java agent"
pip install -r requirements.txt
```

### Step 2: Parse Perl Code and Generate AST
```bash
cd "perl parser"

# Parse your Perl code and generate AST files
python perform_perl_parser.py /path/to/your/perl/files

# AST files will be created in the ./ast/ folder
```

### Step 3: Start Neo4j Database
Make sure you have a Neo4j instance running and accessible.

```bash
# Start Neo4j (if not already running)
neo4j start

# Neo4j should be accessible at http://localhost:7474
```

### Step 4: Write AST to Neo4j
```bash
# Still in "perl parser" directory
# Load AST data from ./ast/ folder into Neo4j database
python neo4j_writer.py
```

### Step 5: Generate Java Code
```bash
cd "../java agent"

# Run main file which uses all imported agents
python main.py

# Generated Java code will be saved in the ./output/ folder
```

## 🔧 What Each Component Does

### Perl Parser Directory
- **`perform_perl_parser.py`**: Main parser that reads Perl source files, analyzes syntax, and generates Abstract Syntax Tree (AST) files
- **`neo4j_writer.py`**: Takes AST files from the `ast/` folder and writes them as nodes and relationships into Neo4j database
- **`ast/`**: Storage location for generated AST files
- **`examples/`**: Sample Perl files for testing the parser

### Java Agent Directory  
- **`main.py`**: Main execution script that orchestrates the Java code generation process using all imported agents
- **`agents/`**: Contains LLM-powered agents that handle different aspects of code generation
- **`config.py`**: Configuration settings for Neo4j connection, LLM API, and generation parameters
- **`state.py`**: Manages the state and context during the migration process
- **`prompts/`**: Contains LLM prompts and templates for code generation
- **`setup.py`**: Handles initialization and setup of the generation environment

## ⚙️ Configuration

### Environment Variables
```bash
# Neo4j connection
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="your_password"

# LLM API (example for OpenAI)
export OPENAI_API_KEY="your_api_key"
```

### Configuration Files
- Edit `java agent/config.py` to set your database connections and API keys
- Modify prompts in `java agent/prompts/` to customize code generation behavior

## 🔄 Complete Workflow Example

```bash
# 1. Navigate to perl parser
cd "perl parser"

# 2. Parse your Perl project
python perform_perl_parser.py /path/to/your/perl/project

# 3. Ensure Neo4j is running
neo4j start

# 4. Write AST to Neo4j
python neo4j_writer.py

# 5. Navigate to java agent
cd "../java agent" 

# 6. Generate Java code
python main.py

# 7. Check generated Java files
ls -la output/
```

## 📊 Neo4j Graph Database

The AST data is stored in Neo4j as a graph with:
- **Nodes**: Representing Perl language constructs (functions, variables, modules, statements)
- **Relationships**: Showing how code elements interact and depend on each other
- **Properties**: Storing detailed information about each code element

## 🤖 LLM Agent System

The Java agent uses multiple specialized agents:
- **Code Analysis Agent**: Understands Perl patterns and idioms
- **Translation Agent**: Converts Perl constructs to Java equivalents  
- **Optimization Agent**: Improves and refines generated Java code
- **Validation Agent**: Checks generated code for correctness

## 🛠️ Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/chmm2/perl_to_java_migration_tool.git
   cd perl_to_java_migration_tool
   ```

2. **Install dependencies for both components**
   ```bash
   cd "perl parser"
   pip install -r requirements.txt
   
   cd "../java agent"
   pip install -r requirements.txt
   ```

3. **Set up Neo4j database**
   - Install and start Neo4j
   - Create database credentials
   - Update configuration files

4. **Configure LLM API access**
   - Get API key from your LLM provider
   - Set environment variables or update config files

## 📝 Example Usage

```bash
# Parse a simple Perl script
cd "perl parser"
python perform_perl_parser.py examples/sample.pl

# Write to Neo4j
python neo4j_writer.py

# Generate Java equivalent
cd "../java agent"
python main.py
```

## 🚨 Requirements

- **Python 3.x** with required packages
- **Neo4j database** (local or remote instance)
- **LLM API access** (OpenAI, Azure OpenAI, or other compatible providers)
- **Sufficient disk space** for AST files and generated Java code

## 🤝 Support

- Check the README.md files in each subdirectory for component-specific documentation
- Review example files in `perl parser/examples/` for usage patterns
- Examine generated logs and output files for debugging

## 📄 License

Please refer to the repository for license information.

---

**Note**: This tool provides automated migration assistance. Manual review and testing of generated Java code is recommended before production use.
