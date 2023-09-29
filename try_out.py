import re


def replace_uuid_except_nth(text):
    pattern = r'UUID\(.*?\)'
    occurrences = len(re.findall(pattern, text))

    for i in range(1, occurrences + 1):
        count = [0]

        def replacer(match):
            count[0] += 1
            return match.group(0) if count[0] == i else 'None'

        replaced_text = re.sub(pattern, replacer, text)
        yield f"Ersetzen Sie alle außer dem {i}. Vorkommen:\n{replaced_text}\n"

# Testen Sie die Funktion
text = 'Dies ist ein Text mit UUID(1234-5678-9101), UUID(1122-3344-5566), UUID(2233-4455-6677) und UUID(3344-5566-7788).'
for t in replace_uuid_except_nth(text):
    print(t)
