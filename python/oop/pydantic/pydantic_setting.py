from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
    model_config=SettingsConfigDict(env_file=".env")
    app_name:str="My_App"
    database_url:str
    gemini_api:str
    
    

setting=Settings()
api=setting.gemini_api
print(api)