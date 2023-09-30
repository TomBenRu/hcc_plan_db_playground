import re
from itertools import combinations


def replace_uuid_except_n(fixed_cast_text):
    pattern = r'UUID\(.*?\)'
    matches = re.findall(pattern, fixed_cast_text)
    occurrences = len(matches)

    for i in range(occurrences + 1):
        for combo in combinations(range(occurrences), i):
            count = [0]
            none_count = [0]

            def replacer(match):
                count[0] += 1
                if count[0] - 1 in combo:
                    return match.group(0)
                else:
                    none_count[0] += 1
                    return f"'None{none_count[0]:02d}'"

            replaced_text = re.sub(pattern, replacer, fixed_cast_text)
            yield replaced_text

# Testen Sie die Funktion
text = 'Dies ist ein Text mit UUID(1234-5678-9101), UUID(1122-3344-5566), UUID(2233-4455-6677) und UUID(3344-5566-7788).'
for replaced_text in replace_uuid_except_n(text):
    print(replaced_text)
