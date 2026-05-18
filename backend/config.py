from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    serpapi_key: str | None = None
    google_service_account_json: str | None = None
    google_drive_folder_id: str | None = None
    google_spreadsheet_id: str | None = None
    openrouteservice_api_key: str | None = None
    sendgrid_api_key: str | None = None
    sendgrid_from_email: str | None = None
    recipient_email: str | None = None
    secret_url_token: str | None = None

    test_mode: bool = False
    test_google_spreadsheet_id: str | None = None
    test_recipient_email: str | None = None


settings = Settings()
