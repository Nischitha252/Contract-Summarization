rr_prompt_template = '''
        You are an expert in document extraction. Your task is to extract questions and answers from sections in the given image where the answers are marked in blue-colored boxes and checkboxes. 
        Remember that the boxes in blue are the correct options. If a page does not have any questions with answers marked in blue or checkboxes, skip it and do print "skip" and nothing else.
        The answers can belong to the sections like customer, our bid, or it be general. Mostly If there is 2 options given in parallel to question one in left and other in right then left one can be 'customer' section and right one can be 'our bid' section.
        Provide the output in the JSON format given below.
        
        ```
        [
        {"section": "1.1 - Business type",
        "question": "What kind of business does this opportunity relate to?",
        "answer": "Energy Solution (except Nuclear & Coal)",
        "page": 4
        },
        {
        "section":"3.2.1 - Select applicable contract type",
        "question": "The degree to which the involvement of customer and/or consultant is required in deciding the technical requirements.",
        "answer": "3",
        "page" : 6
        },
        {
        "section":"3.5.7 - Consequential Losses",
        "question": "Does the contract contain an express exclusion of liability for consequential losses?",
        "answer": {
        "Customer": "Yes",
        "Our bid": "Yes" 
        },
        "page": 9
        },
        {
        "question": "Is the contract regarding consequential losses in line with CFLI-CP-11 (including permitted exemptions)?",
        "answer": {
        "Customer": "No",
        "Our bid": "Yes",
        "page": 12
        }
        },
        {
        "question": "Is the project Gross Result Margin below 21.0%?",
        "answer": "No",
        "page" : 20
        },
        {
        "question": "Is the proposed ABB cash flow calculation negative as defined in Business Area Risk Review Policy?",
        "answer": "No",
        "page" : 27
        }
        ]
        '''