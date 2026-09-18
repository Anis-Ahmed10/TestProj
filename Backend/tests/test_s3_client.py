from unittest.mock import MagicMock, patch

from app.core.s3_client import get_s3_client


@patch("app.core.s3_client.boto3.client")
@patch("app.core.s3_client.get_settings")
def test_get_s3_client(mock_get_settings, mock_boto3_client):
    mock_settings = MagicMock()
    mock_settings.aws_region = "us-east-1"
    mock_get_settings.return_value = mock_settings

    mock_client_instance = MagicMock()
    mock_boto3_client.return_value = mock_client_instance

    client = get_s3_client()

    assert client == mock_client_instance
    mock_boto3_client.assert_called_once()
    call_args = mock_boto3_client.call_args
    assert call_args[0][0] == "s3"
    assert call_args[1]["region_name"] == "us-east-1"
    assert "config" in call_args[1]
