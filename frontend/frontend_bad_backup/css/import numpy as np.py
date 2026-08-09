import numpy as np
data = [10, 20, 30, 40, 50]
sales = np.array(data)
print("1. np.array():", sales)
print("   Type:", type(sales))

print("-" * 40)
total = np.sum(sales)
print("2. np.sum(): Total =", total)  

print("-" * 40)


average = np.mean(sales)
print("3. np.mean(): Average =", average)  

print("-" * 40)

highest = np.max(sales)
print("4. np.max(): Highest =", highest)  # 50

print("-" * 40)

lowest = np.min(sales)
print("5. np.min(): Lowest =", lowest)  # 10

print("-" * 40)


median_val = np.median(sales)
print("6. np.median(): Median =", median_val)  # 30.0

print("-" * 40)

std_dev = np.std(sales)
print("7. np.std(): Standard Deviation =", round(std_dev, 2))

print("-" * 40)

sorted_sales = np.sort(sales)
print("8. np.sort(): Sorted =", sorted_sales)