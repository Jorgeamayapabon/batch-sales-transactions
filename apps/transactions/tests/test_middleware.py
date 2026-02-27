import logging
from unittest.mock import MagicMock
from apps.transactions.middleware import ResponseTimeMiddleware, log_response_time


class TestResponseTimeMiddleware:
    def test_middleware_calls_get_response(self):
        get_response = MagicMock(return_value=MagicMock(status_code=200))
        middleware = ResponseTimeMiddleware(get_response)
        request = MagicMock()
        request.path = "/api/test/"
        request.method = "GET"

        middleware(request)
        get_response.assert_called_once_with(request)

    def test_middleware_returns_response(self):
        mock_response = MagicMock(status_code=201)
        get_response = MagicMock(return_value=mock_response)
        middleware = ResponseTimeMiddleware(get_response)
        request = MagicMock()
        request.path = "/api/test/"
        request.method = "POST"

        result = middleware(request)
        assert result is mock_response

    def test_middleware_logs_response_time(self, caplog):
        mock_response = MagicMock(status_code=200)
        get_response = MagicMock(return_value=mock_response)
        middleware = ResponseTimeMiddleware(get_response)
        request = MagicMock()
        request.path = "/api/transactions/batch/"
        request.method = "POST"

        with caplog.at_level(logging.INFO, logger="transactions.middleware"):
            middleware(request)

        assert len(caplog.records) == 1
        assert "duration_ms" in caplog.records[0].message
        assert "/api/transactions/batch/" in caplog.records[0].message


class TestLogResponseTimeDecorator:
    def test_decorator_preserves_function_name(self):
        def my_view(self, request):
            return MagicMock(status_code=200)

        decorated = log_response_time(my_view)
        assert decorated.__name__ == "my_view"

    def test_decorator_returns_response(self):
        mock_response = MagicMock(status_code=200)
        mock_request = MagicMock()
        mock_request.method = "POST"

        def my_view(self, request):
            return mock_response

        decorated = log_response_time(my_view)
        result = decorated(None, mock_request)
        assert result is mock_response

    def test_decorator_logs_on_call(self, caplog):
        mock_response = MagicMock(status_code=201)
        mock_request = MagicMock()
        mock_request.method = "POST"

        def batch_view(self, request):
            return mock_response

        decorated = log_response_time(batch_view)

        with caplog.at_level(logging.INFO, logger="transactions.middleware"):
            decorated(None, mock_request)

        assert len(caplog.records) == 1
        assert "duration_ms" in caplog.records[0].message
        assert "POST" in caplog.records[0].message
