def generate_id(db:dict)->int:
    if not db:
        return 1
    return max(db.keys()) + 1



def record_exists(db:dict, id:int)->bool:
    return id in db

def get_all_records(db:dict)->dict:
    return db

def delete_record(db:dict,id:int)->None:
    del db[id]

def update_record(db:dict,id:int,record:dict)->None:
    db[id]=record
    
def format_success_message(action:str,resourse:str,id:int)->dict:
    return {"message":f"{resourse} with id {id} has been {action} successfully."}