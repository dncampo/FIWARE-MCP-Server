# Additional model providers and local runtimes

This is a proposed next phase, not an executed experiment. Gemini and local
models have no PASS results in this repository yet. The generic MCP server and
its seven tools should remain unchanged.

## Preserve the shared experiment contract

Reuse the exact question bank, instruction prompts, fixture/context hashes,
read-only policy and reviewer criteria used by the dated Claude/Codex baseline.
Every question starts a fresh conversation. Expected answers remain outside the
model's context. Retain native MCP calls, arguments, actual broker responses,
client/model settings and unsuccessful results. Do not count model-generated
answers without tool execution as an MCP integration test.

Keep new model/client dependencies optional and outside the server's production
requirements. Extend launchers and archive parsing minimally rather than adding
an application agent or orchestration framework.

## Gemini

Use Gemini CLI as an independent native MCP client. Its official documentation
supports STDIO MCP, per-server includeTools allowlists, and headless stream-json
output containing tool_use and tool_result events:

* [MCP configuration](https://geminicli.com/docs/tools/mcp-server/)
* [Headless output](https://geminicli.com/docs/cli/headless/)
* [API-key authentication](https://geminicli.com/docs/get-started/authentication/)

An existing Google AI Studio key can be supplied through GEMINI_API_KEY. Keep it
out of prompts, source files, MCP child configuration and published evidence.
Use the chosen model ID explicitly and record the actual model reported by the
client. Pin and verify the installed CLI version before implementing its parser;
do not assume its settings or event schema are identical to Claude or Codex.

The provider API is remote inference; STDIO still keeps the FIWARE MCP connection
local. No public broker/MCP endpoint is needed. Only read tools should be exposed,
and built-in shell, file and web capabilities must be excluded for evaluation.
Confirm the installed CLI can enforce that isolation before running scored tests.

Gemini CLI was not found in the inspected environment. No installation, key use,
model call or Gemini connectivity test was performed during this research.

## Local models

LM Studio can host MCP servers for local models and supports native MCP use via
its API in supported versions. Reusing that client avoids creating a custom
tool-execution agent:

* [MCP host support](https://lmstudio.ai/docs/app/mcp)
* [MCP via the native API](https://lmstudio.ai/docs/developer/core/mcp)
* [Tool-use support and model templates](https://lmstudio.ai/docs/developer/openai-compat/tools)

Ollama supports model tool calling, but a tool-calling API alone is not an MCP
client. Any Ollama experiment still needs a clearly identified MCP-capable host:

* [Ollama tool calling](https://docs.ollama.com/capabilities/tool-calling)
* [Context length and memory](https://docs.ollama.com/context-length)

Do not assume parameter count alone predicts correct tool use. Compare a small
tool-capable model, an intermediate model and a larger model only when hardware
permits. Record the exact weights/model digest, total and active parameter counts
where applicable, quantization, runtime version, prompt/chat template, context
length, decoding settings, hardware, memory use and CPU/GPU offloading. Keep
timeouts and context truncation visible; an exhausted context is not necessarily
an MCP server defect.

A 70-billion-parameter model at four bits requires approximately 35 GB for raw
weight bits alone, before quantization metadata, runtime overhead and KV cache.
This arithmetic is not a hardware compatibility guarantee. Context length can
materially increase memory requirements. Do not download a large model or make
hardware recommendations before checking actual available memory and runtime.

Ollama and LM Studio command paths were found locally. One Gemma MLX 4-bit model
was found in the LM Studio model directory. Installation presence is not proof of
loaded model, supported MCP operation or successful tool use. No local model was
loaded, downloaded or evaluated. Reading hardware memory was denied by the
managed session; hardware selection remains pending.

## Suggested order

1. Publish the reviewed Claude/Codex baseline and reproducible question runners.
2. Add Gemini CLI with the same 16 questions and its own recorded client/parser.
3. Verify a currently installed local model and MCP host on three smoke questions:
   discovery, numeric filtering and relationship traversal.
4. Run the full bank on supported local configurations, then compare dated
   reviewed archives. Preserve failures and do not silently give a weaker model
   easier questions while presenting it as the same experiment.

Client/model combinations are the experimental units. A native Claude-versus-
Codex-versus-Gemini-versus-LM Studio comparison does not isolate model quality
from host behavior. A future controlled-host experiment would be separate and
must retain its own provenance and limitations.
