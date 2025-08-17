// challenges-data.js
// 7 new challenges to add to MongoDB

const challengesData = [
  {
    title: "Thử Thách Sáo Trúc: Bài Hát Dân Ca",
    description: "Quay video thể hiện kỹ năng thổi sáo trúc với một bài hát dân ca Việt Nam tự chọn. Thời lượng tối thiểu 1 phút.",
    points: 30,
    thumbnail: "/assets/images/challenges/challenge_folk_song.jpg",
    type: "practice_video",
    active: true
  },
  {
    title: "Thử Thách Đàn Tranh: Kỹ Thuật Rung Dây",
    description: "Thực hiện và quay video kỹ thuật rung dây đàn tranh với 3 mức độ khác nhau: nhẹ, vừa và mạnh.",
    points: 25,
    thumbnail: "/assets/images/challenges/challenge_dan_tranh.jpg",
    type: "practice_video",
    active: true
  },
  {
    title: "Thử Thách Vovinam: Đòn Chân Tấn Công",
    description: "Thực hiện chính xác và quay video kỹ thuật đòn chân tấn công trong Vovinam. Chú ý đến tư thế, góc đá và lực.",
    points: 35,
    thumbnail: "/assets/images/challenges/challenge_vovinam_kick.jpg",
    type: "practice_video",
    active: true
  },
  {
    title: "Thử Thách Lý Thuyết Âm Nhạc",
    description: "Hoàn thành bài kiểm tra 15 câu hỏi về lý thuyết âm nhạc cơ bản, bao gồm các nốt nhạc, nhịp điệu và hòa âm.",
    points: 20,
    thumbnail: "/assets/images/challenges/challenge_music_theory.jpg",
    type: "quiz",
    active: true
  },
  {
    title: "Thử Thách Sáng Tạo: Biến Tấu Giai Điệu",
    description: "Tạo một biến tấu sáng tạo từ một giai điệu truyền thống và quay video trình diễn. Hãy giải thích cách bạn thay đổi giai điệu gốc.",
    points: 40,
    thumbnail: "/assets/images/challenges/challenge_creative.jpg",
    type: "practice_video",
    active: true
  },
  {
    title: "Thử Thách Võ Thuật: Bài Quyền Cơ Bản",
    description: "Thực hiện và quay video một bài quyền cơ bản trong võ thuật bạn đang học. Chú ý đến tư thế, nhịp điệu và sự chính xác của các động tác.",
    points: 30,
    thumbnail: "/assets/images/challenges/challenge_martial_form.jpg",
    type: "practice_video",
    active: true
  },
  {
    title: "Thử Thách Flashcards: Thuật Ngữ Chuyên Ngành",
    description: "Hoàn thành bài kiểm tra 20 flashcards về thuật ngữ chuyên ngành trong lĩnh vực bạn đang học (nhạc cụ hoặc võ thuật).",
    points: 25,
    thumbnail: "/assets/images/challenges/challenge_terminology.jpg",
    type: "flashcard_test",
    active: true
  }
];

module.exports = challengesData;
