class bank:
    bank_name="mcb bank"
    def __init__(self, name, balance,password):
        self.name = name
        self.balance = balance
        self.password = password
    
    def deposit(self,amount):
        self.balance += amount
        print(f"Deposited {amount}. New balance is {self.balance}.")
    def withdraw(self,amount):
        if amount > self.balance:
            print("Insufficient funds.")
        else:
            self.balance -= amount
            print(f"Withdrew {amount}. New balance is {self.balance}.")
    def show_balance(self):
        return self.balance
    @classmethod
    def change_name(cls,c_name):
        cls.bank_name=c_name
        return "name has changed succesfully"
    @classmethod
    def convert_string(cls,p_data):
        person_name,person_balance,person_password=p_data.split(",")
        person_balance=int(person_balance)
        return cls(person_name,person_balance,person_password)
    @staticmethod
    def validate_amount(amount):
        if amount <= 0:
            raise ValueError("Amount must be positive.")
        return True
    @staticmethod
    def password_check(password):
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        elif not any(char.isdigit() for char in password):
            raise ValueError("Password must contain at least one digit.")
        return True
data="ahmad,100,passwor"




ahmad=bank.convert_string(data)

real_amount=bank.validate_amount(ahmad.balance)
valid_password=bank.password_check(ahmad.password)

ahmad.deposit(200)

print(ahmad.password)
print(ahmad.balance)





