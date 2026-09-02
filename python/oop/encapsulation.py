class bank:
    def __init__(self, balance):
        self._balance = balance
        
    def deposit(self, amount):
        if amount > 0:
            self._balance += amount
            print(f"Deposited: {amount}. New balance: {self._balance}")
        else:
            print("Deposit amount must be positive.")

    def change_balance(self, new_balance):
        if isinstance(new_balance, (int, float)) and new_balance >= 0:
            self._balance = new_balance
            print(f"Balance changed to: {self._balance}")
        
        else:
            print("Balance cannot be negative or non-numeric.")
        
        
    def show_balance(self):
        print(f"Current balance: {self._balance}")

bank1=bank(500)
bank1.change_balance(1000)
bank1.show_balance()


