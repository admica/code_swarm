# Project Dependency Graph

## Visualization

```mermaid
graph TB
    %% Node styles
    classDef python fill:#2b5b84,stroke:#1a365d,color:#fff,stroke-width:2px;
    classDef lua fill:#000080,stroke:#000066,color:#fff,stroke-width:2px;
    classDef heavy_deps fill:#8b0000,stroke:#580000,color:#fff,stroke-width:3px;
    classDef light_deps fill:#006400,stroke:#004100,color:#fff,stroke-width:1px;

    %% Link styles
    linkStyle default stroke:#666,stroke-width:1px;
    subgraph shared[shared]
    direction TB
        shared_llm.py[llm]:::light_deps
        shared_base_agent.py[base_agent]:::python
        shared_file_monitor.py[file_monitor]:::light_deps
        shared_models.py[models]:::light_deps
        shared___init__.py[__init__]:::light_deps
        shared_config.py[config]:::light_deps
        shared_agent_logger.py[agent_logger]:::light_deps
        shared_logging.py[logging]:::light_deps
    end
    subgraph frontend_node_modules_flatted_python[python]
    direction TB
        frontend_node_modules_flatted_python_flatted.py[flatted]:::light_deps
        frontend_node_modules_flatted_python_test.py[test]:::light_deps
    end

    %% Root directory files
    agent_code_mon_readme.py[agent_code_m...]:::python
    agent_code_mon_changelog.py[agent_code_m...]:::python
    agent_code_mon_deps.py[agent_code_m...]:::python
    agent_swarm_controller.py[agent_swarm_...]:::python
    setup.py[setup]:::python
    agent_test.py[agent_test]:::python
    run.py[run]:::python

    %% Dependencies
    agent_code_mon_readme.py ==> shared___init__.py
    agent_code_mon_readme.py ==> shared_base_agent.py
    agent_code_mon_readme.py ==> shared_file_monitor.py
    agent_code_mon_changelog.py ==> shared___init__.py
    agent_code_mon_deps.py ==> shared_base_agent.py
    agent_code_mon_deps.py ==> shared_file_monitor.py
    agent_code_mon_deps.py ==> shared___init__.py
    agent_swarm_controller.py ==> shared_llm.py
    agent_swarm_controller.py ==> shared_config.py
    agent_swarm_controller.py ==> shared_models.py
    agent_test.py ==> shared_base_agent.py
    agent_test.py ==> shared_file_monitor.py
    agent_test.py ==> shared___init__.py
    shared_base_agent.py ==> shared_agent_logger.py
```

## Dependencies

### agent_code_mon_readme.py

Depends on:
- shared/__init__.py
- shared/base_agent.py
- shared/file_monitor.py

### agent_code_mon_changelog.py

Depends on:
- shared/__init__.py

### agent_code_mon_deps.py

Depends on:
- shared/base_agent.py
- shared/file_monitor.py
- shared/__init__.py

### agent_swarm_controller.py

Depends on:
- shared/llm.py
- shared/config.py
- shared/models.py

### setup.py

No dependencies

### agent_test.py

Depends on:
- shared/base_agent.py
- shared/file_monitor.py
- shared/__init__.py

### run.py

No dependencies

### frontend/node_modules/flatted/python/flatted.py

No dependencies

### frontend/node_modules/flatted/python/test.py

No dependencies

### shared/llm.py

No dependencies

### shared/base_agent.py

Depends on:
- shared/agent_logger.py

### shared/file_monitor.py

No dependencies

### shared/models.py

No dependencies

### shared/__init__.py

No dependencies

### shared/config.py

No dependencies

### shared/agent_logger.py

No dependencies

### shared/logging.py

No dependencies
