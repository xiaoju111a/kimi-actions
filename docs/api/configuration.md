# Configuration API

## Action Inputs

### kimi_api_key
- **Required**: Yes
- **Description**: Kimi API key from Moonshot AI

### github_token
- **Required**: Yes
- **Description**: GitHub token for API access

### language
- **Required**: No
- **Default**: `en-US`
- **Options**: `en-US`, `zh-CN`

### model
- **Required**: No
- **Default**: `kimi-k2-thinking`
- **Options**: `kimi-k2-thinking`, `kimi-k2-turbo-preview`

### review_level
- **Required**: No
- **Default**: `normal`
- **Options**: `strict`, `normal`, `gentle`

### max_files
- **Required**: No
- **Default**: `50`
- **Description**: Maximum number of files to review
