from pydantic import BaseModel,Field,field_validator
class User(BaseModel):
    id:int=Field(gt=0)
    password:str
    name:str=Field(min_length=3,max_length=20)
    
    
    @field_validator("password")
    @classmethod
    def validate_password(cls, value):
        if not any (char.isdigit() for char in value):
            raise ValueError("Password must contain at least one digit.")
        elif not any (char.isupper() for char in value):
            raise ValueError("Password must contain at least one uppercase letter.")
        return value
user=User(id="12",name="salman",password="Salman123")


print(user.id)





