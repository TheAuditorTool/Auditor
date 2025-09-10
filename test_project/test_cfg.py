"""Test file for CFG extraction."""

def simple_function(x):
    """Simple function with no control flow."""
    y = x + 1
    return y

def function_with_if(x):
    """Function with if-else statement."""
    if x > 0:
        result = x * 2
    else:
        result = -x
    return result

def function_with_loop(items):
    """Function with for loop."""
    total = 0
    for item in items:
        total += item
    return total

def function_with_nested(x, items):
    """Function with nested control structures."""
    result = 0
    
    if x > 0:
        for item in items:
            if item > x:
                result += item * 2
            else:
                result += item
    else:
        result = -1
    
    return result

def function_with_try(x):
    """Function with try-except."""
    try:
        result = 10 / x
    except ZeroDivisionError:
        result = 0
    finally:
        print("Done")
    
    return result

def complex_function(data, threshold):
    """Complex function with multiple control structures."""
    results = []
    errors = 0
    
    for item in data:
        if item is None:
            errors += 1
            continue
        
        try:
            if item > threshold:
                processed = item * 2
                
                if processed > 100:
                    results.append(processed)
                else:
                    while processed < 50:
                        processed += 10
                    results.append(processed)
            else:
                results.append(item)
        except Exception as e:
            errors += 1
            print(f"Error: {e}")
    
    if errors > 0:
        print(f"Processed with {errors} errors")
    
    return results