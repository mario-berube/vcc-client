from utils import make_object

data = {'link': "http://google.com"}

obj = make_object(data)

print(obj.link)
print(type(obj))
