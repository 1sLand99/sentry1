from unittest.mock import patch

from sentry.llm.usecases import LLMUseCase, complete_prompt


def test_complete_prompt(set_sentry_option) -> None:
    with (
        set_sentry_option(
            "llm.provider.options",
            {"vertex": {"models": ["vertex-1.0"], "options": {"url": "fake_url"}}},
        ),
        set_sentry_option(
            "llm.usecases.options",
            {"example": {"provider": "vertex", "options": {"model": "vertex-1.0"}}},
        ),
        patch(
            "sentry.llm.providers.vertex.VertexProvider._get_access_token",
            return_value="fake_token",
        ),
        patch(
            "requests.post",
            return_value=type(
                "obj",
                (object,),
                {
                    "status_code": 200,
                    "json": lambda x: {
                        "candidates": [
                            {
                                "content": {
                                    "role": "model",
                                    "parts": [
                                        {
                                            "text": "hellogemini",
                                            "finishReason": "STOP",
                                            "avgLogprobs": -4.491923997799556e-06,
                                        }
                                    ],
                                    "modelVersion": "vertex-1.0",
                                }
                            }
                        ]
                    },
                },
            )(),
        ),
    ):
        res = complete_prompt(
            usecase=LLMUseCase.EXAMPLE,
            prompt="prompt here",
            message="message here",
            temperature=0.0,
            max_output_tokens=1024,
        )
    assert res == "hellogemini"
