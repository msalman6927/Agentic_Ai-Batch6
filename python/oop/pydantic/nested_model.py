from typing import Optional

from pydantic import BaseModel
class Address(BaseModel):
    street:str
    city: str
    state: str
    zip_code: str
    
class person(BaseModel):
    routine:list[dict]      #[{"day":"monday","task":"coding"},{"day":"tuesday","task":"reading"}]
    name:str
    age:int
    address:Address
    skill:Optional[str]=None
    
    
person_info='{"name":"ahmad","age":30,"address":{"street":"street123","city":"lahore","state":"Punjab","zip_code":"54000"},"skill":"python"}'

ali=person.model_validate_json(person_info)
print(ali.model_dump_json())

ali=person(name="ali",age=25,address=Address(street="stree123",city="sahiwal",state="Punjab",zip_code="50000"),skill="python")
# print(ali.model_dump_json())
# print(ali)

# print(ali.name)
# print(ali.address.city)


# print(ali.skill)

#serialization



