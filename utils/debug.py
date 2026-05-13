from config import DEBUG
import pprint

def debug(title, data):

    if not DEBUG:
        return

    print("\n" + "=" * 60)
    print(title)

    if isinstance(data, (dict, list)):
        pprint.pprint(data)
    else:
        print(data)

    print("=" * 60 + "\n")
