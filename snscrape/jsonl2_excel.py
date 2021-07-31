import jsonl module (assuming it's located in the CWD)
import jsonl
import csv
import json
import datetime


begin_time = datetime.datetime.now()

# parse dataset to list of dictionaries
dataset = jsonl.parse('a.jsonl')

# parse JSONL with indentations 
def parse(filename):
    # list of items
    items = []

    # open JSONL file
    with open(filename, 'r') as f:
        # remove first and last two characters
        data = f.read()[1:-2]
        
        # extract JSON items  
        data = data.split('}\n{')
        print('intial data')
        # loop over data items  
        for item in data:
            # parse item to python dictionary type
            item_dict = json.loads('{' + item + '}')
            
            # append parsed item to item list
            items.append(item_dict)
        
        # return list of parsed items
        return items

# tests 
if __name__ == '__main__':
    # call parse
    data = parse('a.jsonl')
print(datetime.datetime.now() - begin_time)
length=len(data)
x=length
for i in range(len(data)) :
    data1=data[i]
    print(i)
    res={key:data1[key]for key in data1.keys()&{'url','content','date','media','renderedContent',}}
    with open('output1.csv','a')as output:
         writer=csv.writer(output)
         for key,value in res.items():
             writer.writerow([key,value])
          

print(datetime.datetime.now() - begin_time)



          
          
          
          
          
          
          
          
          
          
          
          
          
          
          
          
          
          
          
          
          
          
          
          
          
          
          
          
          
