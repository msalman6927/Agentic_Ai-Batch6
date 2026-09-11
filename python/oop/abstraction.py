from abc import ABC ,abstractmethod
class Vehicle(ABC): 
    def __init__(self,brand):
        self.brand=brand
    #abstract class
    @abstractmethod
    def start(self):
        pass
    @abstractmethod
    def stop(self):
        pass
    
    def show_brand(self):
        print(f"Brand name is{self.brand}")
class car(Vehicle):
    def start(self):
       
        print("Car started")
        
    def stop(self):
        print("Car stopped")

class bike(Vehicle):
    def start(self):
        print("Bike started")
        
    def stop(self):
        print("Bike stopped")
        

car1=car("Civic")
bike1=bike("Honda 70")

for vehicle in (car1,bike1):
    vehicle.show_brand()
    vehicle.show_brand()
