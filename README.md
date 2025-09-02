# MuleSoft Migration Assessment Tool

A tool for analyzing MuleSoft codebases to assess migration complexity and feasibility. This tool extracts key metrics without exposing actual source code, making it safe for clients to share the generated reports with their technology partner.

## Quick Start

### Guided Script (Recommended)
```bash
chmod +x start.sh
./start.sh
```

## Prerequisites

Before running the assessment tool, ensure you have the following installed:

- **git** - For cloning repositories
- **jq** - For JSON parsing
- **python3** - For running the analysis
- **zip** - For creating final packages
- **curl** - For GitHub API access

### Installation Commands

**macOS:**
```bash
brew install git jq python3 zip curl
```

**Ubuntu/Debian:**
```bash
sudo apt-get install git jq python3 zip curl
```

**CentOS/RHEL:**
```bash
sudo yum install git jq python3 zip curl
```

### GitHub Personal Access Token

You'll need a GitHub Personal Access Token with appropriate permissions:

1. Go to GitHub Settings > Developer settings > Personal access tokens
2. Click 'Generate new token'
3. Select required permissions:
   - **repo** (for private repositories)
   - **read:org** (for organization access)
4. Copy the token for use in the script

## Usage

### Guided Mode (Recommended)

Run the automated script and follow the prompts:

```bash
./start.sh
```

The script will guide you through:
1. **GitHub Authentication** - Enter your Personal Access Token
2. **Instance Selection** - Choose GitHub.com or GitHub Enterprise
3. **Organization Selection** - Specify the GitHub organization
4. **Repository Discovery** - Automatically find MuleSoft projects
5. **Download Management** - Download repositories
6. **Multi-source Support** - Add repositories from multiple organizations/instances
7. **Assessment Generation** - Analyze all collected projects

### Manual Mode

If the automated script can not be used:

```bash
python3 migration_assessment.py /path/to/projects \
  --output-dir assessment_results \
  --individual-files \
  --projects project1 project2
```

#### Command Line Options

- `repo_folder` - Path to folder containing MuleSoft repositories (required)
- `--output-dir` - Output directory for analysis files (default: report_output)
- `--individual-files` - Generate individual JSON files for each project
- `--projects` - Analyze only specific project names
- `--help` - Show detailed help information

## Output Files

### Assessment Reports

The tool generates several report types:

**JSON Reports:**
- `mulesoft_analysis_analysis.json` - Comprehensive analysis data
- `{project_name}_analysis.json` - Individual project details (if using --individual-files)

**Human-Readable Reports:**
- `mulesoft_analysis_comprehensive.txt` - Summary and detailed analysis
- `mulesoft_analysis_summary.txt` - High-level overview and recommendations

**Final Package:**
- `mulesoft_migration_assessment_YYYYMMDD_HHMMSS.zip` - Complete assessment package

### Report Contents

**Summary:**
- Project count and Mule version distribution
- Migration complexity overview
- High-level recommendations

**Technical Analysis:**
- XML tags and component usage
- Connector complexity scores
- Custom code analysis
- DataWeave transformation analysis
- Large file identification

**Project Details:**
- Individual project breakdowns
- Flow and component statistics
- Testing coverage analysis
- Complexity indicators

## Security & Privacy

The assessment tool is designed with security in mind:

- **No source code exposure** - Only analyzes structure and metadata
- **Secure authentication** - Uses GIT_ASKPASS for token handling
- **Safe to share** - Generated reports contain no proprietary code
- **Token cleanup** - Temporary authentication scripts are automatically removed

## Troubleshooting

### Common Issues

**Permission Denied:**
```bash
chmod +x start.sh
```

**Missing Dependencies:**
- Install all prerequisites listed above
- Verify installations with `command -v git jq python3 zip curl`

**GitHub Authentication Failures:**
- Verify token has correct permissions
- Check organization access
- Ensure token hasn't expired

**No MuleSoft Projects Found:**
- Check directory structure requirements
- Verify `src/main/mule` exists with `.xml` files
- Ensure `pom.xml` or `mule-artifact.json` present

## Next Steps

After completing the assessment:

1. **Review Reports** - Examine the comprehensive analysis
2. **Complete Forms** - Answer the questions in "Client Questionnaire.pdf"
3. **Share Results** - Send the ZIP and the questionnaire responses to your technology partner

## Author & Copyright

**Author:** Juan Heyns <juan.heyns@epiuse.com>  
**Copyright:** (c) 2025, Group Elephant. All rights reserved.

---

*This tool is designed to facilitate MuleSoft migration assessments while maintaining security and confidentiality of your source code.*
