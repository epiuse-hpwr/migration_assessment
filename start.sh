#!/bin/bash

# MuleSoft Migration Assessment Runner
# This script guides users through downloading MuleSoft projects and generating migration assessment reports

# Author: Juan Heyns <juan.heyns@epiuse.com>
# (c) copyright 2025, EPI-USE America, Inc. All rights reserved.

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE} ${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE} ${NC}"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
check_prerequisites() {
    print_header "Checking Prerequisites"
    
    local missing_deps=()
    
    if ! command_exists git; then
        missing_deps+=("git")
    fi
    
    if ! command_exists jq; then
        missing_deps+=("jq")
    fi
    
    if ! command_exists python3; then
        missing_deps+=("python3")
    fi
    
    if ! command_exists zip; then
        missing_deps+=("zip")
    fi
    
    if [ ${#missing_deps[@]} -ne 0 ]; then
        print_error "Missing required dependencies: ${missing_deps[*]}"
        echo "Please install the missing dependencies and try again."
        exit 1
    fi
    
    print_status "All prerequisites are installed ✓"
}

# Function to get GitHub token
get_github_token() {
    print_header "GitHub Authentication"
    
    echo "This script will download MuleSoft projects from GitHub organizations."
    echo "You'll need a GitHub Personal Access Token with appropriate permissions."
    echo ""
    echo "Required permissions:"
    echo "  - repo (for private repositories)"
    echo "  - read:org (for organization access)"
    echo ""
    echo "To create a token:"
    echo "  1. Go to GitHub Settings > Developer settings > Personal access tokens"
    echo "  2. Click 'Generate new token'"
    echo "  3. Select the required permissions"
    echo "  4. Copy the token"
    echo ""
    
    read -p "Enter your GitHub token: " -s GITHUB_TOKEN
    echo ""
    
    if [ -z "$GITHUB_TOKEN" ]; then
        print_error "GitHub token is required"
        exit 1
    fi
    
    # Test the token
    print_status "Testing GitHub token..."
    local user_response
    user_response=$(curl -s -H "Authorization: token $GITHUB_TOKEN" "$GITHUB_API_BASE/user")
    
    if echo "$user_response" | jq -e 'type == "object"' > /dev/null; then
        print_status "GitHub token is valid ✓"
        local username
        username=$(echo "$user_response" | jq -r '.login // "Unknown"')
        print_status "Authenticated as: $username"
    else
        print_error "Invalid GitHub token. Please check your token and try again."
        print_error "Response: $(echo "$user_response" | jq -r '.message // "Unknown error"')"
        exit 1
    fi
}

# Function to get GitHub instance type
get_github_instance() {
    print_header "GitHub Instance"
    
    echo "Select your GitHub instance type:"
    echo "1. GitHub.com (public GitHub)"
    echo "2. GitHub Enterprise (self-hosted or GitHub Enterprise Cloud)"
    echo ""
    
    read -p "Enter your choice (1 or 2): " GITHUB_CHOICE
    
    case $GITHUB_CHOICE in
        1)
            GITHUB_API_BASE="https://api.github.com"
            GITHUB_WEB_BASE="https://github.com"
            GITHUB_SSH_HOST="github.com"
            print_status "Using GitHub.com ✓"
            ;;
        2)
            print_status "GitHub Enterprise selected"
            echo ""
            echo "Enter your GitHub Enterprise instance URL."
            echo "Examples:"
            echo "  - https://github.company.com"
            echo "  - https://github.yourdomain.com"
            echo "  - https://yourcompany.github.com"
            echo ""
            read -p "GitHub Enterprise URL: " GITHUB_ENTERPRISE_URL
            
            if [ -z "$GITHUB_ENTERPRISE_URL" ]; then
                print_error "GitHub Enterprise URL is required"
                exit 1
            fi
            
            # Remove trailing slash if present
            GITHUB_ENTERPRISE_URL="${GITHUB_ENTERPRISE_URL%/}"
            
            # Construct API URL
            GITHUB_API_BASE="$GITHUB_ENTERPRISE_URL/api/v3"
            GITHUB_WEB_BASE="$GITHUB_ENTERPRISE_URL"
            
            # Extract hostname for SSH (remove https://)
            GITHUB_SSH_HOST="${GITHUB_ENTERPRISE_URL#https://}"
            GITHUB_SSH_HOST="${GITHUB_SSH_HOST#http://}"
            
            print_status "Using GitHub Enterprise: $GITHUB_ENTERPRISE_URL ✓"
            ;;
        *)
            print_error "Invalid choice. Please enter 1 or 2."
            exit 1
            ;;
    esac
}

# Function to get GitHub organization
get_github_org() {
    print_header "GitHub Organization"
    
    echo "Enter the GitHub organization name where the MuleSoft projects are located."
    if [ "$GITHUB_CHOICE" = "1" ]; then
        echo "Example: 'mycompany' for github.com/mycompany"
    else
        echo "Example: 'mycompany' for $GITHUB_WEB_BASE/mycompany"
    fi
    echo ""
    
    read -p "GitHub organization name: " GITHUB_ORG
    
    if [ -z "$GITHUB_ORG" ]; then
        print_error "Organization name is required"
        exit 1
    fi
    
    # Test organization access
    print_status "Testing organization access..."
    local org_response
    org_response=$(curl -s -H "Authorization: token $GITHUB_TOKEN" "$GITHUB_API_BASE/orgs/$GITHUB_ORG")
    
    if echo "$org_response" | jq -e 'type == "object"' > /dev/null; then
        print_status "Organization access confirmed ✓"
        local org_name
        org_name=$(echo "$org_response" | jq -r '.name // .login // "Unknown"')
        print_status "Organization: $org_name"
    else
        print_error "Cannot access organization '$GITHUB_ORG'. Please check the name and your permissions."
        print_error "Response: $(echo "$org_response" | jq -r '.message // "Unknown error"')"
        exit 1
    fi
}

# Function to discover MuleSoft repositories
discover_mulesoft_repos() {
    print_header "Discovering MuleSoft Repositories"
    
    print_status "Searching for MuleSoft repositories in organization '$GITHUB_ORG'..."
    
    # Create temporary file for repository list
    REPO_LIST_FILE=$(mktemp)
    
    # Get all repositories from the organization (with pagination)
    print_status "Fetching repositories (this may take a while for large organizations)..."
    
        print_status "Will scan all repositories (this may take a while for large organizations)"
    
    local page=1
    local per_page=100
    local all_repos="[]"
    
    while true; do
        print_status "Fetching page $page..."
        
        local api_response
        api_response=$(curl -s -H "Authorization: token $GITHUB_TOKEN" \
             "$GITHUB_API_BASE/orgs/$GITHUB_ORG/repos?per_page=$per_page&page=$page&type=all")
        
        # Check if API call was successful and response is an array
        if echo "$api_response" | jq -e 'type == "array"' > /dev/null; then
            local repo_count
            repo_count=$(echo "$api_response" | jq 'length')
            
            if [ "$repo_count" -eq 0 ]; then
                print_status "No more repositories found (end of pagination)"
                break
            fi
            
            # Merge with existing repos
            all_repos=$(echo "$all_repos" | jq -s '.[0] + .[1]' <(echo "$all_repos") <(echo "$api_response"))
            
            print_status "Found $repo_count repositories on page $page"
            
            
            
            # If we got fewer repos than requested, we've reached the end
            if [ "$repo_count" -lt "$per_page" ]; then
                break
            fi
            
            ((page++))
        else
            print_error "Failed to fetch repositories from GitHub API"
            print_error "Response: $(echo "$api_response" | jq -r '.message // "Unknown error"')"
            print_error "Full response: $api_response"
            exit 1
        fi
    done
    
    # Extract repository names from the combined response
    local total_repos
    total_repos=$(echo "$all_repos" | jq 'length')
    print_status "Total repositories found: $total_repos"
    
    echo "$all_repos" | jq -r '.[] | select(.archived == false or .archived == null) | .name' > "$REPO_LIST_FILE"
    
    # Filter for MuleSoft repositories (look for common patterns)
    print_status "Scanning repositories for MuleSoft projects..."
    
    local total_repos_to_check
    total_repos_to_check=$(wc -l < "$REPO_LIST_FILE")
    local checked_count=0
    local mulesoft_count=0
    
    MULESOFT_REPOS=()
    while IFS= read -r repo; do
        if [ -n "$repo" ]; then
            ((checked_count++))

            # Check if repository contains MuleSoft files with proper structure
            local repo_contents
            repo_contents=$(curl -s -H "Authorization: token $GITHUB_TOKEN" \
                    "$GITHUB_API_BASE/repos/$GITHUB_ORG/$repo/contents")
            
            if echo "$repo_contents" | jq -e 'type == "array"' > /dev/null; then
                # First check for basic MuleSoft indicators
                if echo "$repo_contents" | jq -e '.[] | select(.name | test("mule-artifact\\.json|pom\\.xml"))' > /dev/null; then
                    # Check for src/main/mule folder structure
                    local src_check
                    src_check=$(curl -s -H "Authorization: token $GITHUB_TOKEN" \
                            "$GITHUB_API_BASE/repos/$GITHUB_ORG/$repo/contents/src")
                    
                    if echo "$src_check" | jq -e 'type == "array"' > /dev/null; then
                        local main_check
                        main_check=$(curl -s -H "Authorization: token $GITHUB_TOKEN" \
                                "$GITHUB_API_BASE/repos/$GITHUB_ORG/$repo/contents/src/main")
                        
                        if echo "$main_check" | jq -e 'type == "array"' > /dev/null; then
                            local mule_check
                            mule_check=$(curl -s -H "Authorization: token $GITHUB_TOKEN" \
                                    "$GITHUB_API_BASE/repos/$GITHUB_ORG/$repo/contents/src/main/mule")
                            
                            if echo "$mule_check" | jq -e 'type == "array"' > /dev/null; then
                                # Check if there are any .xml files in src/main/mule
                                if echo "$mule_check" | jq -e '.[] | select(.name | test("\\.xml$"))' > /dev/null; then
                                    MULESOFT_REPOS+=("$repo")
                                    ((mulesoft_count++))
                                    print_status "✓ Found MuleSoft project: $repo"
                                fi
                            fi
                        fi
                    fi
                fi
            else
                print_warning "Cannot access repository contents for: $repo"
            fi
            
            # Show progress every 10 repositories
            if [ $((checked_count % 10)) -eq 0 ]; then
                print_status "Progress: $checked_count/$total_repos_to_check repositories checked, $mulesoft_count MuleSoft projects found"
            fi
        fi
    done < "$REPO_LIST_FILE"
    
    print_status "Repository scanning complete: $checked_count repositories checked, $mulesoft_count MuleSoft projects found"
    
    rm "$REPO_LIST_FILE"
    
    if [ ${#MULESOFT_REPOS[@]} -eq 0 ]; then
        print_warning "No MuleSoft repositories found in organization '$GITHUB_ORG'"
        echo "This could mean:"
        echo "  - No MuleSoft projects exist in this organization"
        echo "  - Projects are in private repositories you don't have access to"
        echo "  - Projects don't have the expected MuleSoft file structure"
        echo ""
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    else
        print_status "Found ${#MULESOFT_REPOS[@]} MuleSoft repositories:"
        for repo in "${MULESOFT_REPOS[@]}"; do
            echo "  - $repo"
        done
    fi
}

# Function to download repositories
download_repositories() {
    print_header "Downloading MuleSoft Repositories from $GITHUB_ORG"
    
    # Create hierarchical directory structure: projects/github_hostname/org_name
    if [ -z "$PROJECTS_BASE_DIR" ]; then
        PROJECTS_BASE_DIR="projects"
    fi
    
    ORG_PROJECTS_DIR="$PROJECTS_BASE_DIR/$GITHUB_SSH_HOST/$GITHUB_ORG"
    mkdir -p "$ORG_PROJECTS_DIR"
    cd "$ORG_PROJECTS_DIR"
    
    print_status "Downloading repositories to '$ORG_PROJECTS_DIR'..."
    
    local downloaded_count=0
    
    # Test repository access first
    print_status "Testing repository access..."
    local test_repo
    test_repo="${MULESOFT_REPOS[0]}"
    if [ -n "$test_repo" ]; then
        print_status "Testing access to: $test_repo"
        
        # Test HTTPS with token
        if curl -s -H "Authorization: token $GITHUB_TOKEN" "$GITHUB_API_BASE/repos/$GITHUB_ORG/$test_repo" | jq -e 'type == "object"' > /dev/null; then
            print_status "✓ Repository access confirmed via API"
        else
            print_warning "⚠️  Repository access may be limited"
        fi
    fi
    
    # Create temporary askpass script
    ASKPASS_SCRIPT=$(mktemp)
    cat > "$ASKPASS_SCRIPT" << 'EOF'
#!/bin/bash
echo "$GITHUB_TOKEN"
EOF
    chmod +x "$ASKPASS_SCRIPT"

    for repo in "${MULESOFT_REPOS[@]}"; do
        print_status "Downloading $repo..."
        
        # Try different authentication methods
        local clone_success=false
        
        # HTTPS with token using GIT_ASKPASS
        if ! $clone_success; then
            print_status "  Trying HTTPS with token..."
            if GIT_ASKPASS="$ASKPASS_SCRIPT" timeout 60 git clone --quiet "$GITHUB_WEB_BASE/$GITHUB_ORG/$repo.git" 2>/dev/null; then
                print_status "✓ Downloaded $repo (HTTPS with token)"
                ((downloaded_count++))
                clone_success=true
            fi
            
            # Clean up temporary script
            rm -f "$ASKPASS_SCRIPT"
        fi
        
        if ! $clone_success; then
            print_warning "Failed to download $repo (HTTPS with token)"
            print_warning "  - Repository may be private and require different authentication"
            print_warning "  - Token may not have sufficient permissions"
            print_warning "  - Token may have expired"
        fi
    done

    # Clean up temporary script
    rm -f "$ASKPASS_SCRIPT"
    
    # If no repositories were downloaded, offer manual download option
    if [ "$downloaded_count" -eq 0 ]; then
        echo ""
        print_warning "No repositories were downloaded automatically."
        echo ""
        echo "Manual download options:"
        echo "1. Download repositories manually and continue"
        echo "2. Skip repository download and exit"
        echo ""
        read -p "Choose option (1-2): " manual_choice
        
        case $manual_choice in
            1)
                echo ""
                echo "Please manually download the MuleSoft repositories to maintain the hierarchical structure:"
                echo "Structure: projects/$GITHUB_SSH_HOST/$GITHUB_ORG/REPO_NAME"
                echo ""
                echo "Create the directory structure first:"
                echo "  mkdir -p projects/$GITHUB_SSH_HOST/$GITHUB_ORG"
                echo "  cd projects/$GITHUB_SSH_HOST/$GITHUB_ORG"
                echo ""
                echo "Then clone repositories:"
                if [ "$GITHUB_CHOICE" = "1" ]; then
                    echo "For GitHub.com:"
                    echo "  git clone https://github.com/$GITHUB_ORG/REPO_NAME.git"
                    echo "  git clone git@github.com:$GITHUB_ORG/REPO_NAME.git"
                else
                    echo "For GitHub Enterprise:"
                    echo "  git clone $GITHUB_ENTERPRISE_URL/$GITHUB_ORG/REPO_NAME.git"
                    echo "  git clone git@$GITHUB_SSH_HOST:$GITHUB_ORG/REPO_NAME.git"
                fi
                echo ""
                echo "MuleSoft repositories found:"
                for repo in "${MULESOFT_REPOS[@]}"; do
                    echo "  - $repo"
                done
                echo ""
                read -p "Press Enter when you have downloaded the repositories..."
                
                # Check if any repositories were downloaded in the hierarchical structure
                local downloaded_dirs
                downloaded_dirs=$(find "$PROJECTS_BASE_DIR" -mindepth 3 -maxdepth 3 -type d | wc -l)
                if [ "$downloaded_dirs" -gt 0 ]; then
                    print_status "Found $downloaded_dirs downloaded repositories"
                    downloaded_count=$downloaded_dirs
                else
                    print_error "No repositories found in projects directory structure"
                    exit 1
                fi
                ;;
            2)
                print_status "Exiting without repository download"
                exit 0
                ;;
            *)
                print_error "Invalid choice"
                exit 1
                ;;
        esac
    fi
    
    print_status "Downloaded $downloaded_count repositories from $GITHUB_ORG"
    # Return to base directory
    cd "$OLDPWD"
}

# Function to handle multiple source downloads
download_multiple_sources() {
    print_header "Repository Download Management"
    
    # Initialize base projects directory
    PROJECTS_BASE_DIR="projects"
    
    while true; do
        # Ask if user wants to download repositories or proceed to assessment
        echo "Repository options:"
        echo "1. Download repositories from GitHub or GitHub Enterprise"
        echo "2. Proceed to analysis (using existing local repositories)"
        echo ""
        
        read -p "Choose option (1-2): " download_choice
        
        case $download_choice in
            1)
                # Get GitHub instance and credentials
                get_github_instance
                get_github_token
                get_github_org
                
                # Discover and download repositories
                discover_mulesoft_repos
                
                if [ ${#MULESOFT_REPOS[@]} -gt 0 ]; then
                    download_repositories
                else
                    print_warning "No MuleSoft repositories found in $GITHUB_ORG"
                fi
                
                # Show current repository count
                if [ -d "$PROJECTS_BASE_DIR" ]; then
                    local total_repos
                    total_repos=$(find "$PROJECTS_BASE_DIR" -name "*.git" -type d | wc -l)
                    if [ "$total_repos" -eq 0 ]; then
                        total_repos=$(find "$PROJECTS_BASE_DIR" -mindepth 3 -maxdepth 3 -type d | wc -l)
                    fi
                    print_status "Total repositories collected: $total_repos"
                    
                    if [ "$total_repos" -gt 0 ]; then
                        echo "Current repositories:"
                        find "$PROJECTS_BASE_DIR" -mindepth 3 -maxdepth 3 -type d | sed 's|^projects/||' | sed 's/^/  - /'
                    fi
                fi
                
                # Ask if user wants to add more sources
                echo ""
                read -p "Do you want to download from another GitHub organization or instance? (y/N): " -n 1 -r
                echo ""
                if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                    break
                fi
                ;;
            2)
                print_status "Using existing local repositories"
                echo ""
                echo "Enter path to existing MuleSoft projects directory."
                echo "This can be either:"
                echo "  - A hierarchical 'projects' directory (projects/hostname/org/repo)"
                echo "  - A flat directory containing MuleSoft projects"
                echo ""
                read -p "Path to projects directory: " existing_projects_path
                
                if [ -n "$existing_projects_path" ] && [ -d "$existing_projects_path" ]; then
                    PROJECTS_BASE_DIR="$existing_projects_path"
                    print_status "Using existing projects at: $PROJECTS_BASE_DIR"
                    
                    # Check for hierarchical structure first
                    local total_repos
                    total_repos=$(find "$PROJECTS_BASE_DIR" -mindepth 3 -maxdepth 3 -type d 2>/dev/null | wc -l)
                    
                    # If no hierarchical structure, check for flat structure
                    if [ "$total_repos" -eq 0 ]; then
                        total_repos=$(find "$PROJECTS_BASE_DIR" -maxdepth 1 -type d -name "*" 2>/dev/null | grep -v "^\.$" | wc -l)
                        if [ "$total_repos" -gt 0 ]; then
                            print_status "Found $total_repos repositories in flat directory structure"
                        fi
                    else
                        print_status "Found $total_repos repositories in hierarchical directory structure"
                    fi
                    
                    if [ "$total_repos" -gt 0 ]; then
                        break
                    else
                        print_error "No MuleSoft projects found in the specified directory"
                        echo ""
                        read -p "Go back to download repositories instead? (y/N): " -n 1 -r
                        echo ""
                        if [[ $REPLY =~ ^[Yy]$ ]]; then
                            continue
                        else
                            exit 1
                        fi
                    fi
                else
                    print_error "Invalid path or directory does not exist"
                    continue
                fi
                ;;
            *)
                print_error "Invalid choice. Please enter 1 or 2."
                ;;
        esac
    done
    
    # Final summary
    if [ -d "$PROJECTS_BASE_DIR" ]; then
        local final_count
        final_count=$(find "$PROJECTS_BASE_DIR" -mindepth 3 -maxdepth 3 -type d | wc -l)
        print_status "Ready to assess $final_count repositories"
        
        # Set PROJECTS_DIR for the assessment script
        PROJECTS_DIR="$PROJECTS_BASE_DIR"
    fi
}

# Function to run the migration assessment
run_migration_assessment() {
    print_header "Running Migration Assessment"
    
    if [ ! -f "migration_assessment.py" ]; then
        print_error "migration_assessment.py not found in current directory"
        exit 1
    fi
    
    print_status "Running MuleSoft Migration Assessment..."
    
    # Create output directory with timestamp
    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    OUTPUT_DIR="migration_assessment_$TIMESTAMP"
    
    # Run the assessment
    if python3 migration_assessment.py "$PROJECTS_DIR" --output-dir "$OUTPUT_DIR"; then
        print_status "Migration assessment completed successfully ✓"
    else
        print_error "Migration assessment failed"
        exit 1
    fi
}

# Function to create final package
create_final_package() {
    print_header "Creating Final Package"
    
    # Create zip file
    ZIP_NAME="mulesoft_migration_assessment_$TIMESTAMP.zip"
    
    print_status "Creating zip package: $ZIP_NAME"
    
    if zip -r "$ZIP_NAME" "$OUTPUT_DIR" > /dev/null; then
        print_status "Package created successfully: $ZIP_NAME"
        
        # Show package contents
        echo ""
        echo "Package contents:"
        unzip -l "$ZIP_NAME" | grep -E "\.(txt|json|md)$" | head -10
        
        echo ""
        print_status "Your migration assessment is ready!"
        echo "File: $ZIP_NAME"
        echo "Size: $(du -h "$ZIP_NAME" | cut -f1)"
        echo ""
        echo "You can now share this file with your technology partner."
    else
        print_error "Failed to create zip package"
        exit 1
    fi
}

# Function to show summary
show_summary() {
    print_header "Assessment Summary"
    
    echo "Assessment completed successfully!"
    echo ""
    echo "Summary:"
    echo "  - Output directory: $OUTPUT_DIR"
    echo "  - Final package: $ZIP_NAME"
    echo ""
    echo "Next steps:"
    echo " - Review the generated reports in $OUTPUT_DIR/"
    echo " - Share the $ZIP_NAME file with your technology partner"
    echo " - Complete the 'Client Questionaire' form"
}

# Main execution
main() {
    print_header "MuleSoft Migration Assessment Tool"
    
    echo "This script will help you:"
    echo " - Download MuleSoft projects from GitHub"
    echo " - Run migration assessment analysis"
    echo " - Package results for sharing"
    echo ""
    
    # Check prerequisites
    check_prerequisites
    
    # Handle multiple source downloads
    download_multiple_sources
    
    # Run assessment
    run_migration_assessment
    
    # Create final package
    create_final_package
    
    # Show summary
    show_summary
}

# Check if jq is installed for JSON parsing
if ! command_exists jq; then
    print_error "jq is required for JSON parsing. Please install jq and try again."
    echo "Installation:"
    echo "  macOS: brew install jq"
    echo "  Ubuntu/Debian: sudo apt-get install jq"
    echo "  CentOS/RHEL: sudo yum install jq"
    exit 1
fi

# Run main function
main "$@" 