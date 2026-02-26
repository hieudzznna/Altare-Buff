import sys
import os

# 1. Thêm đường dẫn thư mục dự án
path = '/home/truehieu/TrueAlt'
if path not in sys.path:
    sys.path.append(path)

# 2. Thiết lập môi trường nếu cần (tùy chọn)
os.chdir(path)

# 3. Import object 'app' từ file web.py
# Vì trong web.py anh đặt là: app = Flask(__name__)
from web import app as application
