class account:
    def __init__(self, balance,name,id):
        self.name=name            #public
        self._balance = balance   #protected
        self.__id=id              #private

        
    def deposit(self, amount):
        if amount > 0:
            self._balance += amount
            print(f"Deposited: {amount}. New balance: {self._balance}")
        else:
            print("Deposit amount must be positive.")
    
    def withdraw(self, amount):
        if 0 < amount <= self._balance+1000:
            self._balance -= amount
            print(f"Withdrew: {amount}. New balance: {self._balance}")
        else:
            print("Invalid withdrawal amount.")

    def change_balance(self, new_balance):
        if isinstance(new_balance, (int, float)) and new_balance >= 0:
            self._balance = new_balance
            print(f"Balance changed to: {self._balance}")
        
        else:
            print("Balance cannot be negative or non-numeric.")
        
        
    def show_balance(self):
        print(f"Current balance: {self._balance}")
class saving_account(account):
    def __init__(self, balance,name,id,interest_rate,withdrawal_limit):
        super().__init__(balance,name,id)
        self.interest_rate=interest_rate
        self.withdrawal_limit=withdrawal_limit

    def calculate_interest(self):
        interest = self._balance * (self.interest_rate / 100)
        print(f"Interest earned: {interest}")
        return interest
    def change_balance(self, new_balance):
        if new_balance < self.withdrawal_limit:
            print(f"Cannot change balance. New balance {new_balance} is below the withdrawal limit of {self.withdrawal_limit}.")
        else:
            super().change_balance(new_balance)
    def withdraw(self, amount):
        if 0<=amount<=self._balance+2000:
            self._balance -= amount
        else:
            print("Invalid withdrawal amount. It exceeds the allowed limit.")
account1=saving_account(1000,"salman","001")
account1.withdraw(500)

saving_account1=saving_account(500,"salman","001",5,1000)
saving_account2=saving_account(1000,"ali","002",7,1500)
saving_account2.change_balance(1200)
saving_account1.change_balance(1000)
saving_account1.withdraw(3001)
print(saving_account1.show_balance())

# print(saving_account2.__id)


# saving_account1.change_balance(1000)
# bank1.show_balance()
