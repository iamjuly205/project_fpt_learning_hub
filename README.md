# FPT Learning Hub

Ứng dụng học tập trực tuyến cho sinh viên FPT.

## Cài đặt

1. Clone repository
2. Cài đặt dependencies:
```
npm install
```

3. Tạo file .env với nội dung:
```
MONGODB_URI=mongodb://localhost:27017/fpt-learning-hub
JWT_SECRET=your_jwt_secret
PORT=5001
```

4. Seed dữ liệu mẫu vào MongoDB:
```
node web/backend/seed-data.js
```

5. Chạy ứng dụng:
```
npm start
```

## API Endpoints

### Flashcards
- GET `/api/flashcards?category=sao` - Lấy danh sách flashcards theo category

### Courses
- GET `/api/courses` - Lấy danh sách tất cả khóa học
- GET `/api/courses?category=Vovinam` - Lấy danh sách khóa học theo category
- GET `/api/courses/:id` - Lấy thông tin chi tiết của một khóa học

### Users
- GET `/api/users?role=student` - Lấy danh sách sinh viên
- GET `/api/users/:id` - Lấy thông tin chi tiết của một người dùng

### Submissions
- GET `/api/submissions?status=pending&type=challenge` - Lấy danh sách bài nộp đang chờ chấm điểm
- POST `/api/submissions` - Tạo bài nộp mới
- POST `/api/submissions/:id/review` - Chấm điểm bài nộp

## Lưu ý

- Dữ liệu mockdata đã được chuyển sang MongoDB
- Cần triển khai đầy đủ các API endpoints để ứng dụng hoạt động đúng
- Không sử dụng dữ liệu mẫu trong code nữa, tất cả dữ liệu được lấy từ MongoDB
