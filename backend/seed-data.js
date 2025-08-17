/**
 * Script để seed dữ liệu mẫu vào MongoDB
 * Chạy script này để xóa dữ liệu cũ và thêm dữ liệu mới vào MongoDB
 * 
 * Cách chạy: node seed-data.js
 */

const { MongoClient, ObjectId } = require('mongodb');
require('dotenv').config();

// Kết nối MongoDB
const uri = process.env.MONGODB_URI || 'mongodb://localhost:27017/fpt-learning-hub';
const client = new MongoClient(uri);

// Dữ liệu mẫu cho flashcards
const flashcardsData = {
    sao: [
        { id: 'sao1', front: 'Sáo trúc là gì?', back: 'Nhạc cụ hơi truyền thống của Việt Nam, làm từ ống trúc' },
        { id: 'sao2', front: 'Kỹ thuật thổi sáo cơ bản', back: 'Đặt môi vào lỗ thổi, điều chỉnh hơi thở và ngón tay trên các lỗ bấm' },
        { id: 'sao3', front: 'Các nốt cơ bản trên sáo', back: 'Đô, Rê, Mi, Fa, Sol, La, Si với các biến thể nửa cung' }
    ],
    'dan-tranh': [
        { id: 'dt1', front: 'Đàn tranh có bao nhiêu dây?', back: 'Truyền thống có 16 dây, hiện đại có thể có 17-19 dây' },
        { id: 'dt2', front: 'Kỹ thuật gảy đàn tranh', back: 'Gảy, véo, vỗ, vuốt, rung' },
        { id: 'dt3', front: 'Cách lên dây đàn tranh', back: 'Sử dụng chìa khóa điều chỉnh độ căng của dây để tạo ra các nốt chuẩn' }
    ],
    'dan-nguyet': [
        { id: 'dn1', front: 'Đàn nguyệt còn gọi là gì?', back: 'Đàn kìm hoặc nguyệt cầm' },
        { id: 'dn2', front: 'Đàn nguyệt có mấy dây?', back: 'Có 2 dây chính' },
        { id: 'dn3', front: 'Thân đàn nguyệt làm từ gì?', back: 'Gỗ quý như gỗ mun, gỗ trắc hoặc gỗ dâu' }
    ],
    vovinam: [
        { id: 'vn1', front: 'Vovinam được sáng lập năm nào?', back: 'Năm 1938 bởi Nguyễn Lộc' },
        { id: 'vn2', front: 'Các đòn chân đặc trưng của Vovinam', back: 'Đá tạt, đá đạp, đá bay, đá lẹo, đòn chân tấn công' },
        { id: 'vn3', front: 'Màu đai trong Vovinam', back: 'Trắng, xanh lam, vàng, đỏ, nâu, đen (từ thấp đến cao)' }
    ]
};

// Dữ liệu mẫu cho courses
const coursesData = [
    {
        _id: new ObjectId('507f1f77bcf86cd799439011'),
        title: 'Sáo Trúc Cơ Bản',
        description: 'Khóa học nhập môn về cách cầm sáo, thổi hơi và các nốt cơ bản.',
        category: 'Nhạc cụ dân tộc',
        thumbnail: './assets/images/courses/sao_truc_cb.jpg',
        video_url: 'https://www.youtube.com/embed/dQw4w9WgXcQ',
        theory_url: 'https://docs.google.com/document/d/1QOSk82iV3gMGAmJXd3vYc78pEgu0vC-ghm_fCY83XDA/edit?usp=sharing'
    },
    {
        _id: new ObjectId('507f1f77bcf86cd799439012'),
        title: 'Kỹ Thuật Láy Sáo',
        description: 'Nâng cao kỹ thuật chơi sáo với các kỹ thuật láy hơi, rung hơi.',
        category: 'Nhạc cụ dân tộc',
        thumbnail: './assets/images/courses/sao_truc_nc.jpg',
        video_url: 'https://www.youtube.com/embed/dQw4w9WgXcQ',
        theory_url: 'https://docs.google.com/document/d/1QOSk82iV3gMGAmJXd3vYc78pEgu0vC-ghm_fCY83XDA/edit?usp=sharing'
    },
    {
        _id: new ObjectId('507f1f77bcf86cd799439013'),
        title: 'Đàn Tranh Cơ Bản',
        description: 'Khóa học nhập môn về cách gảy đàn tranh và các bài tập cơ bản.',
        category: 'Nhạc cụ dân tộc',
        thumbnail: './assets/images/courses/dan_tranh_cb.jpg',
        video_url: 'https://www.youtube.com/embed/dQw4w9WgXcQ',
        theory_url: 'https://docs.google.com/document/d/1W6IkS7mXwusxT9YVDnVmS5BgPptAGPDpqaQirUXWK3g/edit?usp=sharing'
    },
    {
        _id: new ObjectId('507f1f77bcf86cd799439014'),
        title: 'Đàn Nguyệt Cơ Bản',
        description: 'Khóa học nhập môn về cách gảy đàn nguyệt và các bài tập cơ bản.',
        category: 'Nhạc cụ dân tộc',
        thumbnail: './assets/images/courses/dan_nguyet_cb.jpg',
        video_url: 'https://www.youtube.com/embed/dQw4w9WgXcQ',
        theory_url: 'https://docs.google.com/document/d/e/2PACX-1vQw_7WLcUWLEJUUxbPUJdBJT7k2qgRBQyM-cXwU-XAJRpqPcKgFYQ_YvxQkYsoXbQ/pub?embedded=true'
    },
    {
        _id: new ObjectId('507f1f77bcf86cd799439015'),
        title: 'Vovinam Nhập Môn',
        description: 'Khóa học nhập môn về các tư thế, thế tấn và kỹ thuật cơ bản của Vovinam.',
        category: 'Vovinam',
        thumbnail: './assets/images/courses/vovinam_cb.jpg',
        video_url: 'https://www.youtube.com/embed/dQw4w9WgXcQ',
        theory_url: 'https://docs.google.com/document/d/1FAGHDPYsAlvV2pcg77kYY3yFsglInz_adRnTDYqoZ6A/edit?usp=sharing'
    },
    {
        _id: new ObjectId('507f1f77bcf86cd799439016'),
        title: 'Vovinam Nâng Cao',
        description: 'Khóa học nâng cao về các đòn tấn công, phản đòn và tự vệ trong Vovinam.',
        category: 'Vovinam',
        thumbnail: './assets/images/courses/vovinam_nc.jpg',
        video_url: 'https://www.youtube.com/embed/dQw4w9WgXcQ',
        theory_url: 'https://docs.google.com/document/d/e/2PACX-1vQw_7WLcUWLEJUUxbPUJdBJT7k2qgRBQyM-cXwU-XAJRpqPcKgFYQ_YvxQkYsoXbQ/pub?embedded=true'
    }
];

// Hàm chính để seed dữ liệu
async function seedData() {
    try {
        await client.connect();
        console.log('Connected to MongoDB');
        
        const db = client.db();
        
        // Xóa dữ liệu cũ
        console.log('Deleting old data...');
        await db.collection('flashcards').deleteMany({});
        await db.collection('courses').deleteMany({});
        
        // Chuyển đổi dữ liệu flashcards
        const flashcardsToInsert = [];
        for (const category in flashcardsData) {
            flashcardsData[category].forEach(card => {
                flashcardsToInsert.push({
                    ...card,
                    category,
                    createdAt: new Date(),
                    updatedAt: new Date()
                });
            });
        }
        
        // Thêm dữ liệu mới
        console.log('Inserting new flashcards data...');
        const flashcardsResult = await db.collection('flashcards').insertMany(flashcardsToInsert);
        console.log(`${flashcardsResult.insertedCount} flashcards inserted`);
        
        console.log('Inserting new courses data...');
        const coursesResult = await db.collection('courses').insertMany(coursesData);
        console.log(`${coursesResult.insertedCount} courses inserted`);
        
        console.log('Data seeding completed successfully');
    } catch (err) {
        console.error('Error seeding data:', err);
    } finally {
        await client.close();
        console.log('MongoDB connection closed');
    }
}

// Chạy hàm seed
seedData();
