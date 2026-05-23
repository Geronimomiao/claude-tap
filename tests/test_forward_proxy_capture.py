"""Tests for forward proxy capture filtering."""

from __future__ import annotations

import json

import aiohttp
import pytest
from aiohttp import web

from claude_tap.certs import CertificateAuthority, ensure_ca
from claude_tap.forward_proxy import ForwardProxyServer
from claude_tap.trace import TraceWriter


async def _start_http_upstream(handler) -> tuple[web.AppRunner, int]:
    app = web.Application()
    app.router.add_route("*", "/{path:.*}", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    return runner, port


@pytest.mark.asyncio
async def test_forward_proxy_passes_non_llm_large_response_without_recording(tmp_path) -> None:
    body = b"zip-bytes" * 1024 * 256

    async def upstream_handler(_request: web.Request) -> web.Response:
        return web.Response(body=body, content_type="application/zip")

    upstream_runner, upstream_port = await _start_http_upstream(upstream_handler)
    ca_cert_path, ca_key_path = ensure_ca(tmp_path / "ca")
    writer = TraceWriter(tmp_path / "trace.jsonl")
    session = aiohttp.ClientSession(auto_decompress=False)
    proxy = ForwardProxyServer(
        host="127.0.0.1",
        port=0,
        ca=CertificateAuthority(ca_cert_path, ca_key_path),
        writer=writer,
        session=session,
    )
    proxy_port = await proxy.start()

    try:
        async with aiohttp.ClientSession(auto_decompress=False) as client:
            async with client.get(
                f"http://127.0.0.1:{upstream_port}/world.zip",
                proxy=f"http://127.0.0.1:{proxy_port}",
            ) as resp:
                assert resp.status == 200
                assert await resp.read() == body

        writer.close()
        assert (tmp_path / "trace.jsonl").read_text(encoding="utf-8") == ""
    finally:
        await proxy.stop()
        await session.close()
        await upstream_runner.cleanup()


@pytest.mark.asyncio
async def test_forward_proxy_records_openai_responses_request(tmp_path) -> None:
    async def upstream_handler(_request: web.Request) -> web.Response:
        return web.json_response(
            {
                "id": "resp_forward",
                "model": "gpt-test",
                "output": [{"type": "message", "content": [{"type": "output_text", "text": "ok"}]}],
                "usage": {"input_tokens": 2, "output_tokens": 1},
            }
        )

    upstream_runner, upstream_port = await _start_http_upstream(upstream_handler)
    ca_cert_path, ca_key_path = ensure_ca(tmp_path / "ca")
    trace_path = tmp_path / "trace.jsonl"
    writer = TraceWriter(trace_path)
    session = aiohttp.ClientSession(auto_decompress=False)
    proxy = ForwardProxyServer(
        host="127.0.0.1",
        port=0,
        ca=CertificateAuthority(ca_cert_path, ca_key_path),
        writer=writer,
        session=session,
    )
    proxy_port = await proxy.start()

    try:
        async with aiohttp.ClientSession(auto_decompress=False) as client:
            async with client.post(
                f"http://127.0.0.1:{upstream_port}/v1/responses",
                proxy=f"http://127.0.0.1:{proxy_port}",
                json={"model": "gpt-test", "input": [{"role": "user", "content": "hi"}]},
            ) as resp:
                assert resp.status == 200
                assert (await resp.json())["id"] == "resp_forward"

        writer.close()
        records = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
        assert len(records) == 1
        assert records[0]["request"]["path"] == "/v1/responses"
        assert records[0]["request"]["body"]["model"] == "gpt-test"
        assert records[0]["response"]["body"]["id"] == "resp_forward"
    finally:
        await proxy.stop()
        await session.close()
        await upstream_runner.cleanup()
