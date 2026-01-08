# Configuration Guide

This directory contains all configuration files for the autoammonia system. The configuration system supports multiple experimental setups (currently Toronto and Barcelona) and automatically detects which setup to use based on the computer's hostname.

## Table of Contents

- [Overview](#overview)
- [File Structure](#file-structure)
- [Setup Detection](#setup-detection)
- [Configuration Files](#configuration-files)
- [How to Modify Configurations](#how-to-modify-configurations)
- [Adding a New Setup](#adding-a-new-setup)

## Overview

The configuration system is organized to support multiple experimental setups. Each setup has its own set of configuration files, allowing different hardware configurations, port mappings, and default parameters for each location.

**Key Features:**
- Automatic setup detection based on hostname
- Separate configuration files for each setup
- Easy to add new setups
- Environment variable override for testing

## File Structure

### Core Configuration Files

```
config/
├── setup_mappings.toml          # Maps hostnames to setup names
├── config.py                    # Main config loader and setup detection
├── components_config.py          # Component configuration loader
│
├── components_toronto.toml      # Toronto hardware components
├── components_barcelona.toml    # Barcelona hardware components
│
├── connections_info_toronto.toml    # Toronto port mappings
├── connections_info_barcelona.toml  # Barcelona port mappings
│
├── default_config_toronto.toml      # Toronto default parameters
├── default_config_barcelona.toml    # Barcelona default parameters
│
├── default_config_mock_toronto.toml     # Toronto mock/test parameters
└── default_config_mock_barcelona.toml   # Barcelona mock/test parameters
```

### Legacy Files (No Longer Used)

These files are kept for reference but are not actively used:
- `components.toml`
- `connections_info.toml`
- `default_config.toml`
- `default_config_mock.toml`

## Setup Detection

The system automatically detects which setup to use through the following process:

1. **Environment Variable Check** (highest priority)
   - If `AUTOAMMONIA_SETUP` is set, use that value
   - Example: `export AUTOAMMONIA_SETUP=barcelona`

2. **Hostname Detection**
   - Reads `setup_mappings.toml` to find hostname patterns
   - Compares current hostname against configured patterns
   - Returns the first matching setup

3. **Default Fallback**
   - If no match is found, defaults to `"toronto"`

### Current Hostname Mappings

See `setup_mappings.toml` for current mappings:

```toml
[toronto]
hostnames = ["adrastea"]

[barcelona]
hostnames = ["pc1836"]
```

**To modify hostname mappings:** Edit `setup_mappings.toml` and add hostnames to the appropriate section.

---

## Simulation Mode

The system supports two independent simulation controls via environment variables:

### Environment Variables

1. **`AUTOAMMONIA_SIMULATION`** (Hardware Mocking)
   - Controls whether hardware classes are replaced with mocks
   - `true` = Use mock hardware classes (from `autoammonia.hardware.mock`)
   - `false` = Use real hardware classes
   - Default: `false`

2. **`AUTOAMMONIA_MOCK_CONFIG`** (Config File Selection)
   - Controls which config file is loaded
   - `true` = Load `default_config_mock_{setup}.toml` (fast timings for testing)
   - `false` = Load `default_config_{setup}.toml` (production timings)
   - Default: `false`

### Usage Examples

**Pure Logic Testing (No Hardware, Fast Timings):**
```bash
export AUTOAMMONIA_SIMULATION=true
export AUTOAMMONIA_MOCK_CONFIG=true
pytest tests/unit tests/integration
```

**Fast Hardware Test (Real Hardware, Fast Timings):**
```bash
export AUTOAMMONIA_SIMULATION=false
export AUTOAMMONIA_MOCK_CONFIG=true
pytest tests/hardware -m hardware
```

**Production Mode (Real Hardware, Production Timings):**
```bash
export AUTOAMMONIA_SIMULATION=false
export AUTOAMMONIA_MOCK_CONFIG=false
# Run actual experiments
```

**Note:** These environment variables are automatically set by pytest fixtures for unit/integration tests. Hardware tests can override them using the `hardware_test_mode` fixture.

---

## Configuration Files

### 1. `setup_mappings.toml`

**Purpose:** Maps computer hostnames to setup names.

**Location:** `src/autoammonia/config/setup_mappings.toml`

**When to modify:**
- Adding a new computer for an existing setup
- Adding a new setup location
- Changing which computer belongs to which setup

**Example:**
```toml
[toronto]
hostnames = ["adrastea", "toronto-pc"]

[barcelona]
hostnames = ["pc1836", "barcelona-lab"]
```

---

### 2. `components_{setup}.toml`

**Purpose:** Defines hardware components (pumps, valves, potentiostats, etc.) for each setup.

**Files:**
- `components_toronto.toml`
- `components_barcelona.toml`

**When to modify:**
- Adding new hardware components
- Changing COM ports or device addresses
- Updating hardware class names
- Changing component-specific parameters

**Structure:**
```toml
[component_name]
class = "module.ClassName"
com_port = "/dev/device"  # or "COM4" on Windows
address = 1
# ... other component-specific parameters
```

**Note:** The `[global].simulation` flag has been removed. Simulation mode is now controlled via environment variables (see [Simulation Mode](#simulation-mode) section below).

**Example - Adding a new pump:**
```toml
[longerWE02]
class = "matterlab_pumps.LongerPeristalticPump"
com_port = "/dev/longer_pumps"
address = 3
baudrate = 1200
```

---

### 3. `connections_info_{setup}.toml`

**Purpose:** Defines port mappings, volumes, and connections for each component.

**Files:**
- `connections_info_toronto.toml`
- `connections_info_barcelona.toml`

**When to modify:**
- Changing port assignments (which vial is on which port)
- Updating volume capacities
- Modifying stock solution configurations
- Changing port connection volumes

**Structure:**
```toml
[component_name]
port_name = { port = 1, con_vol = 0.5, volume = 100, max_vol = 500, usage = "stock" }

[setup]
components = ["component1", "component2", ...]  # List of active components
```

**Example - Modifying a port:**
```toml
[tecanRX01]
water = { port = 1, con_vol = 0.64, usage = "stock", volume = 5000, max_vol = 5000 }
# ... other ports
```

---

### 4. `default_config_{setup}.toml`

**Purpose:** Contains default parameters for experiments (timeouts, volumes, speeds, etc.).

**Files:**
- `default_config_toronto.toml`
- `default_config_barcelona.toml`

**When to modify:**
- Changing default experiment parameters
- Adjusting timeout values
- Modifying default volumes or speeds
- Updating reaction conditions

**Structure:**
```toml
# Timeouts
function_timeout = 1500
acquisition_timeout = 900

# Experiment parameters
reaction_time = 960
reaction_current = 28.2743339
# ... many more parameters
```

**Note:** The `simulation` flag has been removed. Mock config selection is now controlled via environment variables (see [Simulation Mode](#simulation-mode) section below).

**Example - Changing reaction time:**
```toml
reaction_time = 1200  # Changed from 960 to 1200 seconds
```

---

### 5. `default_config_mock_{setup}.toml`

**Purpose:** Contains mock/test parameters (usually shorter times for testing).

**Files:**
- `default_config_mock_toronto.toml`
- `default_config_mock_barcelona.toml`

**When to modify:**
- Adjusting test/simulation parameters
- Changing mock experiment durations
- Modifying test timeout values

**Note:** These files are automatically loaded when `AUTOAMMONIA_MOCK_CONFIG=true` environment variable is set (see [Simulation Mode](#simulation-mode) section below).

---

## How to Modify Configurations

### Common Tasks

#### 1. Change a Component's COM Port

**File:** `components_{setup}.toml`

```toml
# Before
[tecanAZ01]
com_port = "COM4"

# After
[tecanAZ01]
com_port = "COM5"
```

#### 2. Update Port Mappings

**File:** `connections_info_{setup}.toml`

```toml
# Before
[tecanRX01]
water = { port = 1, con_vol = 0.64, ... }

# After - water moved to port 2
[tecanRX01]
water = { port = 2, con_vol = 0.64, ... }
```

#### 3. Change Default Experiment Parameters

**File:** `default_config_{setup}.toml`

```toml
# Before
reaction_time = 960

# After
reaction_time = 1200
```

#### 4. Add a New Computer to an Existing Setup

**File:** `setup_mappings.toml`

```toml
[barcelona]
hostnames = ["pc1836", "pc1837"]  # Added new computer
```

#### 5. Enable/Disable Simulation Mode

**Environment Variables** (recommended method):

Simulation mode is now controlled via environment variables, not TOML flags:

```bash
# Enable hardware mocking (uses mock classes instead of real hardware)
export AUTOAMMONIA_SIMULATION=true

# Enable mock config (uses default_config_mock_*.toml with fast timings)
export AUTOAMMONIA_MOCK_CONFIG=true

# Both can be used together or independently
```

**Windows PowerShell:**
```powershell
$env:AUTOAMMONIA_SIMULATION="true"
$env:AUTOAMMONIA_MOCK_CONFIG="true"
```

**Common Combinations:**
- **Pure logic testing**: `SIMULATION=true`, `MOCK_CONFIG=true` (mocked hardware + fast timings)
- **Fast hardware test**: `SIMULATION=false`, `MOCK_CONFIG=true` (real hardware + fast timings)
- **Production**: `SIMULATION=false`, `MOCK_CONFIG=false` (real hardware + production timings)

**Note:** The old TOML-based `simulation` flags have been removed. Use environment variables instead.

---

## Adding a New Setup

To add a completely new setup (e.g., "London"):

### Step 1: Add Hostname Mapping

Edit `setup_mappings.toml`:
```toml
[london]
hostnames = ["london-pc", "uk-lab"]
```

### Step 2: Create Component Configuration

Create `components_london.toml`:
```toml
[component1]
class = "..."
# ... component definitions
```

**Note:** No `[global].simulation` section needed - simulation is controlled via environment variables.

### Step 3: Create Connections Info

Create `connections_info_london.toml`:
```toml
[component1]
port1 = { port = 1, ... }

[setup]
components = ["component1", ...]
```

### Step 4: Create Default Config

Create `default_config_london.toml`:
```toml
# ... all default parameters
# No simulation flag needed - controlled via AUTOAMMONIA_MOCK_CONFIG env var
```

### Step 5: Create Mock Config (Optional)

Create `default_config_mock_london.toml`:
```toml
# ... mock/test parameters
```

**That's it!** The system will automatically detect and load the London setup when running on a computer with a matching hostname.

---

## Important Notes

1. **File Naming Convention:** All setup-specific files follow the pattern `{filename}_{setup}.toml`
   - Example: `components_toronto.toml`, `default_config_barcelona.toml`

2. **Setup Names:** Use lowercase, no spaces (e.g., `toronto`, `barcelona`, `london`)

3. **Simulation Mode:** Controlled via environment variables (not TOML flags):
   - `AUTOAMMONIA_SIMULATION=true` → Uses mock hardware classes instead of real hardware
   - `AUTOAMMONIA_MOCK_CONFIG=true` → Loads `default_config_mock_{setup}.toml` instead of `default_config_{setup}.toml`
   - These can be used independently or together
   - See [Simulation Mode](#5-enabledisable-simulation-mode) section for details

4. **Environment Variable Override:** You can override setup detection by setting:
   ```bash
   export AUTOAMMONIA_SETUP=barcelona  # Linux/Mac
   $env:AUTOAMMONIA_SETUP="barcelona"  # Windows PowerShell
   ```

5. **Backward Compatibility:** The old nested TOML files are no longer used. All configurations should be in setup-specific files.

---

## Troubleshooting

### Setup Not Detected Correctly

1. Check your hostname: `hostname` (Linux/Mac) or `hostname` (Windows)
2. Verify hostname is in `setup_mappings.toml`
3. Use environment variable override to test: `export AUTOAMMONIA_SETUP=barcelona`

### Configuration Not Loading

1. Ensure file names follow the pattern: `{filename}_{setup}.toml`
2. Check that setup name matches exactly (case-sensitive in file names)
3. Verify TOML syntax is correct (no syntax errors)

### Wrong Components Loading

1. Check `connections_info_{setup}.toml` → `[setup].components` list
2. Verify component names match between `components_{setup}.toml` and `connections_info_{setup}.toml`

---

## Quick Reference

| What to Change | Which File |
|---------------|------------|
| Computer hostname mapping | `setup_mappings.toml` |
| Hardware components | `components_{setup}.toml` |
| Port mappings | `connections_info_{setup}.toml` |
| Experiment parameters | `default_config_{setup}.toml` |
| Test/mock parameters | `default_config_mock_{setup}.toml` |
| Override setup detection | Environment variable `AUTOAMMONIA_SETUP` |

---

For questions or issues, refer to the main project documentation or contact the development team.

