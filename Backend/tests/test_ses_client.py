from unittest.mock import MagicMock, patch

from app.core.ses_client import get_ses_client


@patch("app.core.ses_client.boto3.client")
@patch("app.core.ses_client.get_settings")
def test_get_ses_client(mock_get_settings, mock_boto3_client):
    mock_settings = MagicMock()
    mock_settings.aws_region = "us-east-1"
    mock_get_settings.return_value = mock_settings

    mock_client_instance = MagicMock()
    mock_boto3_client.return_value = mock_client_instance

    client = get_ses_client()

    assert client == mock_client_instance
    mock_boto3_client.assert_called_once_with("ses", region_name="us-east-1")
