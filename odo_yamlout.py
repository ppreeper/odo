#!/usr/bin/env python3
import yaml

employee_dict = {
    "employee": {
        "name": "John Doe",
        "age": 35,
        "job": {
            "title": "Software Engineer",
            "department": "IT",
            "years_of_experience": 10,
        },
        "address": {
            "street": "123 Main St.",
            "city": "San Francisco",
            "state": "CA",
            "zip": 94102,
        },
    }
}


print("The python dictionary is:")
print(employee_dict)
yaml_string = yaml.dump(employee_dict)
print("The YAML string is:")
print(yaml_string)

with open("person_data.yaml","w") as fp:
    yaml.dump(employee_dict,fp)
