# This is a test file for Pygments highlighting
def hello_world(name: str = "World"):
    '''A simple greeting function.'''
    greeting = f"Hello, {name}!" # A comment with a ' quote and a " quote.
    print(greeting)
    number = 123_456
    return True

class MyClass:
    pass

if __name__ == "__main__":
    hello_world("Pygments")
