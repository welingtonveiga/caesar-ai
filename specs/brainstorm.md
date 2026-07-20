# Caesar AI

Caesar is a personal AI agent that you can install locally or in a box in the cloud.

## Inspiration

Caesar AI takes its name from Caesar, the legendary leader in the *Planet of the Apes* saga, not the Roman general. The project draws inspiration from his resilience, ethical restraint, strategic judgment, and commitment to long-term stability. Caesar aims to be a capable but principled guardian and coordinator: adaptive to context, decisive when needed, and never reckless in its execution.

## How to create an agent
- You configure your agent based on an agent.yml file in a dedicated folder. The file defines:
    - The name of the agent, default: Caesar
    - The agent's soul - its personality and 'identity'. Default: TBD
    - The main LLM API connection
    - The list of folders it has access to, default: filesystem/ subfolder of the same directory
    - The communication channels you want to enable, default: Telegram (required IDs commented out)
- When you run Caesar, you pass the agent definition directories (you can have multiple agents) as a command-line parameter OR the env var CAESAR_AGENTS, or it will look for agent.yml files in subfolders of the current directory.
- To interact with Caesar, you need to enable channels; the default one is Telegram. It will process messages and talk to the user using the channels.
- If multiple channels are available (Telegram and Slack), Caesar has the context of the previous conversation and can pick up topics from past interactions.

## What Caesar can do
- Caesar can execute code in sandboxes (Apple Container, Docker).
- Caesar can use tools to read files and access the web.
- You can install/create more tools for Caesar (access Google Drive, Read Email, Access Calendar, etc.) by configuring them in the agent.yml file.
    - They will have a defined API; a few of them will be shipped with Caesar, while for others you need to be technical to install/configure/create them.
- You can create skills for Caesar by adding a skills subfolder and following the Claude skills format.
- Caesar will run constantly and should be respawned if the process dies; it should be started with the machine.
- Caesar should be able to work on long-term tasks.
- If idle, Caesar can be proactive and make suggestions, bring up ideas, or just check on the user.
- Caesar remembers previous interactions, preferences, people, places, etc.

## How Caesar works
- It's a Python project using LangGraph.
- It has 4 main 'components':
    - Channels: adapters to messaging/communication channels with the user/other agents.
    - Brain: the gateway to receive messages, process requests, and call tools/skills.
    - Actuators: the tools it has access to, including filesystem access and the ability to execute code in sandboxes.
    - Memory: the mechanism to recover context, record important facts, and remember the user.
- As it is installed as a single dependency, initially it will depend on a database that can be installed with it: SQLite.
- It will save its own memory in a subfolder.
- It promotes a request to a task (with a short task name/ID) only when the request involves sandbox execution, multi-step tool work, or will outlive a single reply; casual chat stays inline in the conversation.
- For ongoing tasks, it can use the subfolder workspace/<task_short_name>/ to save temporary files. 
- Code execution (within a task context):
    - It runs in ephemeral containers based on a prebaked Python image with common packages preinstalled (pandas, numpy, openpyxl, etc.) and networking fully disabled — no internet, no local ports, no runtime pip installs. Missing packages fail gracefully and get added to the image.
    - The input folder (`in/`) is mounted explicitly as **Read-Only (`ro`)**, meaning code can never corrupt or delete seed files. The output directory (`out/`) is mounted as **Read-Write (`rw`)** to intercept target assets. 

## Caesar Memory
- I want to explore the memory as its own module because I want to research and change solutions here, so the memory is behind an abstraction layer.
- The default implementation is LangMem.

## Tool Classification & Execution Governance

To maximize the tool's utility while enforcing safety boundaries, tools are organized into strict operational tiers classified by **blast radius (reversibility)**, not locality, governed by physical infrastructure barriers and dynamic software logic.

### Operational Tier Mapping

| Tier | Category | Operational Examples | Execution Policy |
| :--- | :--- | :--- | :--- |
| **Tier 1** | Reads & Internal Writes | All reads — local file system, web fetch/search, knowledge graphs, workspace structure — plus writes strictly inside Caesar's own folders (workspace/, filesystem/). | **Autonomous (Implicit):** Fired immediately with zero user friction. |
| **Tier 2** | Untrusted Execution | Running generated Python scripts to transform data, parse sheets, or convert file types. | **Autonomous Sandbox:** Fired inside an isolated, unprivileged container. |
| **Tier 3** | External Mutation | Anything that mutates the world outside Caesar's folders: dispatching emails, firing communication webhooks, writes to other host folders, deletes, host-level destructive operations. | **Strict Interruption:** Requires human approval via state breakpoints. |

### Sandboxed Code Execution (Tier 2)
Code generation and processing are isolated using a **Docker Workspace Pattern**:
* **Data Boundaries:** The Gateway mounts specific directories onto the ephemeral container. The input folder (`in/`) is mounted explicitly as **Read-Only (`ro`)**, meaning code can never corrupt or delete seed files. The output directory (`out/`) is mounted as **Read-Write (`rw`)** to intercept target assets.
* **Network Isolation:** Containers run with networking fully disabled — no outbound connections at all. Dependencies come preinstalled in a prebaked, pinned image instead of on-demand installs (container runtimes cannot enforce a registry-only allowlist on their own, and runtime installs execute untrusted build hooks with network access). If code needs a missing package, the run fails gracefully and the package gets added to the image.

### Human-In-The-Loop (HITL) Firewalls (Tier 3)
When the LangGraph state engine encounters a Tier 3 tool payload emitted by the LLM:
* The graph encounters a hard execution **Breakpoint**.
* The current loop halts, persists its frame snapshot to SQLite, and updates the task state to an awaiting status.
* The engine is entirely freed up to accept other non-blocking tasks. Execution resumes only when the respective Channel receives an explicit manual confirmation command, restoring the thread's memory vector exactly where it paused.
