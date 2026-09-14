 ## Recommendation

  Do not replace Ollama solely based on the general statement that “vLLM is faster.”

  For this device:

  - Keep Ollama for the working application.
  - First measure cold-load time, prompt-processing time and generation tokens/second.
  - Prototype vLLM-Metal separately with the equivalent MLX-quantized Qwen model.
  - Compare warm single-request TTFT, tokens/second, total latency and memory.
  - Consider migration only if the benchmark shows a meaningful improvement—roughly 20% or more under the actual
    workload.

  My expectation is that streaming and warm-model management would improve the user experience more than switching
  to vLLM on this M1 8 GB configuration.


####

  No—Kubernetes is not needed for the current product or the initial 10-user deployment.

  For one M5 Mac, Kubernetes would increase operational complexity without adding inference capacity. The main
  bottleneck is the model runtime and unified memory, not container scheduling.

  A better architecture for 10 users is:

  Reverse proxy
       │
  FastAPI API
       │
  PostgreSQL durable queue
       │
  1–2 task workers
       │
  Shared model admission controller
       │
  Ollama or vLLM-Metal

  Docker Compose can run all application components:

  - Frontend
  - API
  - PostgreSQL
  - Qdrant
  - One or two task workers
  - Sandbox runner
  - Metrics service
  - Reverse proxy

  Ollama or vLLM-Metal should continue running natively on macOS for Metal acceleration.

  Kubernetes would not:

  - Make the M5 GPU faster.
  - Create additional unified memory.
  - Allow ten simultaneous generations safely.
  - Automatically make the current in-process task lock distributed.
  - Solve model admission control.
  - Improve availability when everything runs on the same physical Mac.

  Use Kubernetes later if the deployment grows to multiple server machines and you need:

  - Several API and worker replicas.
  - Multiple independent inference nodes or GPUs.
  - Automated placement of workloads on suitable nodes.
  - Rolling deployments and service discovery.
  - Replica recovery across physical hosts.
  - Per-organization isolation.
  - Centralized secrets, policy and observability.
  - High availability with redundant data services.

  Even then, Kubernetes support for Apple Silicon GPU/Metal scheduling is not the normal production path. A more
  likely future topology is Kubernetes for application services on Linux, with dedicated GPU inference servers
  exposed through a private internal API.

  Recommended progression:
  1. Current prototype: Docker Compose and one serialized worker.
  2. 10-user pilot: Docker Compose, durable PostgreSQL queue, 1–2 workers and centralized model admission.
  3. Larger single-site local deployment: Docker Compose on a larger-memory Mac or Linux GPU workstation.
  4. Multiple inference machines or production HA: consider Kubernetes.

  For this project, introducing Kubernetes now would distract from the changes that actually improve capacity:
  durable queueing, streaming, model batching, admission control and load testing.