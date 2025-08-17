// Flashcard data for the application
// Each category has 20 flashcards

const flashcardsData = {
    // Sáo (Bamboo Flute) Flashcards
    "sao": [
        { id: "sao1", front: "Sáo trúc là gì?", back: "Nhạc cụ hơi truyền thống của Việt Nam, làm từ ống trúc" },
        { id: "sao2", front: "Kỹ thuật thổi sáo cơ bản", back: "Đặt môi vào lỗ thổi, điều chỉnh hơi thở và ngón tay trên các lỗ bấm" },
        { id: "sao3", front: "Các nốt cơ bản trên sáo", back: "Đô, Rê, Mi, Fa, Sol, La, Si với các biến thể nửa cung" },
        { id: "sao4", front: "Sáo trúc có bao nhiêu lỗ bấm?", back: "Sáo trúc truyền thống có 6 lỗ bấm chính và 1 lỗ thổi" },
        { id: "sao5", front: "Kỹ thuật láy hơi trong thổi sáo", back: "Kỹ thuật tạo âm thanh rung, luyến láy bằng cách điều chỉnh hơi thở và ngón tay" },
        { id: "sao6", front: "Cách giữ sáo đúng", back: "Giữ sáo ngang, lỗ thổi hướng vào môi, tay trái ở đầu sáo, tay phải ở phần cuối" },
        { id: "sao7", front: "Chất liệu làm sáo trúc", back: "Trúc Bương hoặc trúc Nứa, thường được chọn từ cây trúc 3-5 năm tuổi" },
        { id: "sao8", front: "Âm vực của sáo trúc", back: "Khoảng 2 quãng tám, từ Sol3 đến Sol5 (tùy thuộc vào kích thước sáo)" },
        { id: "sao9", front: "Kỹ thuật thổi nốt cao trên sáo", back: "Tăng áp lực hơi thở và điều chỉnh góc thổi, kết hợp với việc bịt các lỗ bấm phù hợp" },
        { id: "sao10", front: "Cách chọn sáo phù hợp", back: "Dựa vào chất liệu, âm thanh, độ dài, đường kính và tông của sáo" },
        { id: "sao11", front: "Kỹ thuật vibrato trên sáo", back: "Tạo hiệu ứng rung bằng cách rung nhẹ ngón tay trên lỗ bấm hoặc điều chỉnh hơi thở" },
        { id: "sao12", front: "Các loại sáo phổ biến ở Việt Nam", back: "Sáo trúc, sáo mèo, sáo H'mông, tiêu, địch" },
        { id: "sao13", front: "Cách bảo quản sáo trúc", back: "Giữ ở nơi khô ráo, tránh ánh nắng trực tiếp, lau khô sau khi sử dụng, thỉnh thoảng bôi dầu" },
        { id: "sao14", front: "Tác dụng của màng sáo", back: "Tạo âm thanh rung, trầm ấm và đặc trưng cho sáo Việt Nam" },
        { id: "sao15", front: "Cách luyện hơi khi thổi sáo", back: "Tập thở bụng, kiểm soát luồng hơi, tập thổi dài hơi và ổn định" },
        { id: "sao16", front: "Bài tập cơ bản cho người mới học sáo", back: "Tập thổi nốt trơn, luyện ngón, tập thổi gam, thực hành các bài dân ca đơn giản" },
        { id: "sao17", front: "Sự khác biệt giữa sáo Nam và sáo Bắc", back: "Sáo Bắc thường có 6 lỗ, âm sắc trong trẻo; sáo Nam có thêm màng trúc, âm thanh trầm ấm hơn" },
        { id: "sao18", front: "Vai trò của sáo trong dàn nhạc dân tộc", back: "Thường đảm nhận giai điệu chính, tạo không khí, diễn tả cảm xúc và khung cảnh thiên nhiên" },
        { id: "sao19", front: "Các bài nhạc nổi tiếng cho sáo", back: "Trống Cơm, Lý Ngựa Ô, Bèo Dạt Mây Trôi, Hòn Vọng Phu, Trăng Thu Dạ Khúc" },
        { id: "sao20", front: "Kỹ thuật staccato trên sáo", back: "Tạo âm ngắt quãng bằng cách sử dụng lưỡi để ngắt luồng hơi, tạo hiệu ứng nhấn nhá" }
    ],

    // Đàn Tranh (Vietnamese Zither) Flashcards
    "dan-tranh": [
        { id: "dt1", front: "Đàn tranh có bao nhiêu dây?", back: "Truyền thống có 16 dây, hiện đại có thể có 17-19 dây" },
        { id: "dt2", front: "Kỹ thuật gảy đàn tranh", back: "Gảy, véo, vỗ, vuốt, rung" },
        { id: "dt3", front: "Cách lên dây đàn tranh", back: "Sử dụng chìa khóa điều chỉnh độ căng của dây để tạo ra các nốt chuẩn" },
        { id: "dt4", front: "Vị trí ngồi khi chơi đàn tranh", back: "Ngồi thẳng lưng, đàn đặt trên đùi hoặc trên bàn thấp, tay phải gảy, tay trái nhấn dây" },
        { id: "dt5", front: "Chất liệu làm đàn tranh", back: "Thân đàn làm từ gỗ quý như gỗ mít, gỗ vàng tâm; dây làm từ kim loại hoặc nylon" },
        { id: "dt6", front: "Âm vực của đàn tranh", back: "Khoảng 4 quãng tám, từ Đô3 đến Đô7 (tùy thuộc vào số dây)" },
        { id: "dt7", front: "Kỹ thuật nhấn dây đàn tranh", back: "Sử dụng tay trái để nhấn dây tạo ra các nốt luyến, láy và biến âm" },
        { id: "dt8", front: "Nguồn gốc của đàn tranh", back: "Có nguồn gốc từ Trung Quốc, du nhập vào Việt Nam và được cải tiến phù hợp với âm nhạc Việt" },
        { id: "dt9", front: "Vai trò của đàn tranh trong dàn nhạc dân tộc", back: "Thường đảm nhận vai trò độc tấu, hòa tấu và đệm cho các nhạc cụ khác" },
        { id: "dt10", front: "Các thế bàn tay khi gảy đàn tranh", back: "Tay phải: ngón cái, trỏ và giữa gảy dây; tay trái: ngón cái, trỏ, giữa và áp út nhấn dây" },
        { id: "dt11", front: "Kỹ thuật rung (vibrato) trên đàn tranh", back: "Tạo hiệu ứng rung bằng cách nhấn và rung nhẹ dây sau khi gảy" },
        { id: "dt12", front: "Cách bảo quản đàn tranh", back: "Giữ ở nơi khô ráo, tránh ánh nắng trực tiếp, sử dụng bao đàn, nới lỏng dây khi không sử dụng lâu" },
        { id: "dt13", front: "Các bài nhạc nổi tiếng cho đàn tranh", back: "Lưu Thủy, Hành Vân, Tứ Đại Oán, Dạ Cổ Hoài Lang, Vọng Cổ" },
        { id: "dt14", front: "Sự khác biệt giữa đàn tranh Việt Nam và guzheng Trung Quốc", back: "Đàn tranh nhỏ hơn, số dây ít hơn, âm sắc trong trẻo hơn và kỹ thuật chơi phù hợp với âm nhạc Việt Nam" },
        { id: "dt15", front: "Các điệu thức phổ biến trong âm nhạc đàn tranh", back: "Điệu Bắc, điệu Nam, điệu Oán, điệu Xuân" },
        { id: "dt16", front: "Kỹ thuật hoa âm trên đàn tranh", back: "Sử dụng nhiều ngón tay cùng lúc để tạo ra các hợp âm và hòa âm phong phú" },
        { id: "dt17", front: "Cách nhận biết đàn tranh chất lượng", back: "Âm thanh trong, vang, cân bằng; gỗ chắc, không cong vênh; dây đàn đều và dễ điều chỉnh" },
        { id: "dt18", front: "Kỹ thuật láy trên đàn tranh", back: "Tạo hiệu ứng láy bằng cách nhấn dây lên xuống nhanh sau khi gảy" },
        { id: "dt19", front: "Các loại móng gảy đàn tranh", back: "Móng nhựa, móng sừng, móng tre, móng kim loại - mỗi loại tạo âm sắc khác nhau" },
        { id: "dt20", front: "Đàn tranh trong âm nhạc hiện đại", back: "Được sử dụng trong nhạc fusion, nhạc hiện đại kết hợp với nhạc cụ phương Tây và điện tử" }
    ],

    // Đàn Nguyệt (Moon Lute) Flashcards
    "dan-nguyet": [
        { id: "dn1", front: "Đàn nguyệt còn được gọi là gì?", back: "Đàn kìm hoặc nguyệt cầm" },
        { id: "dn2", front: "Đàn nguyệt có bao nhiêu dây?", back: "2 dây, thường được lên dây theo quãng 5 (Sol-Rê)" },
        { id: "dn3", front: "Hình dáng của đàn nguyệt", back: "Thân tròn như mặt trăng, cần dài với các phím đàn" },
        { id: "dn4", front: "Chất liệu làm đàn nguyệt", back: "Thân làm từ gỗ quý như gỗ mít, gỗ dâu; mặt đàn bằng gỗ mỏng hoặc da" },
        { id: "dn5", front: "Kỹ thuật gảy đàn nguyệt", back: "Sử dụng móng gảy (thường làm từ sừng trâu, nhựa hoặc tre) để gảy dây" },
        { id: "dn6", front: "Vai trò của đàn nguyệt trong dàn nhạc dân tộc", back: "Thường đảm nhận vai trò đệm hát, độc tấu và hòa tấu trong các thể loại ca trù, chèo, tuồng" },
        { id: "dn7", front: "Nguồn gốc của đàn nguyệt", back: "Có nguồn gốc từ Trung Quốc (đàn nguyệt cầm), du nhập vào Việt Nam từ thế kỷ 13-14" },
        { id: "dn8", front: "Âm vực của đàn nguyệt", back: "Khoảng 2 quãng tám, phụ thuộc vào cách lên dây và số phím đàn" },
        { id: "dn9", front: "Kỹ thuật nhấn dây đàn nguyệt", back: "Sử dụng các ngón tay trái để nhấn dây tại các phím đàn, tạo ra các nốt nhạc khác nhau" },
        { id: "dn10", front: "Các thế bàn tay khi chơi đàn nguyệt", back: "Tay phải cầm móng gảy, tay trái nhấn phím; người chơi thường ngồi và đặt đàn trên đùi" },
        { id: "dn11", front: "Kỹ thuật rung (vibrato) trên đàn nguyệt", back: "Tạo hiệu ứng rung bằng cách rung nhẹ ngón tay trái sau khi nhấn phím" },
        { id: "dn12", front: "Cách bảo quản đàn nguyệt", back: "Giữ ở nơi khô ráo, tránh ánh nắng trực tiếp, sử dụng bao đàn, nới lỏng dây khi không sử dụng lâu" },
        { id: "dn13", front: "Các bài nhạc nổi tiếng cho đàn nguyệt", back: "Lưu Thủy, Phú Lục, Xuân Phong, các bài trong ca trù và chèo" },
        { id: "dn14", front: "Sự khác biệt giữa đàn nguyệt và đàn tỳ bà", back: "Đàn nguyệt có 2 dây và thân tròn, đàn tỳ bà có 4 dây và thân hình quả lê" },
        { id: "dn15", front: "Các điệu thức phổ biến trong âm nhạc đàn nguyệt", back: "Điệu Bắc, điệu Nam, điệu Oán, thường sử dụng trong ca trù và nhạc cung đình" },
        { id: "dn16", front: "Kỹ thuật láy trên đàn nguyệt", back: "Tạo hiệu ứng láy bằng cách nhấn và thả nhanh ngón tay trái trên phím đàn" },
        { id: "dn17", front: "Cách nhận biết đàn nguyệt chất lượng", back: "Âm thanh trong, vang; gỗ chắc, không cong vênh; phím đàn đều và chính xác" },
        { id: "dn18", front: "Đàn nguyệt trong nghệ thuật ca trù", back: "Là nhạc cụ quan trọng trong bộ ba ca trù (tiêu biểu gồm đàn đáy, phách và đàn nguyệt)" },
        { id: "dn19", front: "Số phím trên đàn nguyệt", back: "Thường có từ 9 đến 12 phím, đôi khi có thể lên đến 15-17 phím trên các đàn hiện đại" },
        { id: "dn20", front: "Đàn nguyệt trong âm nhạc hiện đại", back: "Được sử dụng trong các tác phẩm fusion, kết hợp với nhạc cụ hiện đại và trong các dàn nhạc dân tộc cách tân" }
    ],

    // Vovinam (Vietnamese Martial Art) Flashcards
    "vovinam": [
        { id: "vn1", front: "Vovinam được sáng lập bởi ai?", back: "Nguyễn Lộc (1912-1960)" },
        { id: "vn2", front: "Năm thành lập Vovinam", back: "1938" },
        { id: "vn3", front: "Ý nghĩa của từ Vovinam", back: "Võ (Martial Arts) + Vietnam = Võ Việt Nam" },
        { id: "vn4", front: "Khẩu hiệu chính của Vovinam", back: "Cương Nhu Phối Triển (Sự kết hợp giữa cứng và mềm)" },
        { id: "vn5", front: "Các màu đai trong Vovinam", back: "Trắng, Xanh lam, Xanh lá, Nâu, Đỏ, Đen" },
        { id: "vn6", front: "Đặc trưng kỹ thuật nổi bật của Vovinam", back: "Đòn chân bay (bay người đá), quật ngã và khóa gỡ" },
        { id: "vn7", front: "Thế đứng cơ bản trong Vovinam", back: "Trung bình tấn (hai chân rộng bằng vai, gối hơi cong)" },
        { id: "vn8", front: "Nguyên lý triết học của Vovinam", back: "Nhân, Nghĩa, Trí, Dũng, Liêm, Khiêm" },
        { id: "vn9", front: "Kỹ thuật tấn công chính trong Vovinam", back: "Đấm, đá, chỏ, gối, quật ngã và đòn chân bay" },
        { id: "vn10", front: "Số lượng đòn chân bay cơ bản", back: "21 đòn chân bay cơ bản" },
        { id: "vn11", front: "Tên gọi khác của Vovinam", back: "Việt Võ Đạo (tên gọi từ năm 1964)" },
        { id: "vn12", front: "Trang phục tập luyện Vovinam", back: "Võ phục màu xanh dương, đai buộc theo cấp bậc" },
        { id: "vn13", front: "Ý nghĩa của logo Vovinam", back: "Hình tròn vàng (mặt trời) trên nền xanh (bầu trời), tượng trưng cho sức mạnh và sự phát triển không ngừng" },
        { id: "vn14", front: "Các thế tấn cơ bản trong Vovinam", back: "Trung bình tấn, Đinh tấn, Cung tấn, Chảo mã tấn, Hạc tấn" },
        { id: "vn15", front: "Kỹ thuật tự vệ đặc trưng của Vovinam", back: "Khóa gỡ (nghĩa là khóa và gỡ), gồm các kỹ thuật phản đòn và tự vệ" },
        { id: "vn16", front: "Các bài quyền cơ bản trong Vovinam", back: "Thập tự quyền, Tinh hoa lưỡng nghi kiếm pháp, Ngọc trản quyền, Long hổ quyền" },
        { id: "vn17", front: "Nghi thức chào trong Vovinam", back: "Hai tay chắp trước ngực, tay phải nắm, tay trái mở, tượng trưng cho cương nhu phối triển" },
        { id: "vn18", front: "Vovinam hiện nay phổ biến ở bao nhiêu quốc gia?", back: "Hơn 60 quốc gia trên thế giới" },
        { id: "vn19", front: "Kỹ thuật vật trong Vovinam", back: "Gồm các kỹ thuật quật ngã, vật, khóa và đè địch thủ" },
        { id: "vn20", front: "Mục tiêu rèn luyện của Vovinam", back: "Rèn luyện thân thể, trí tuệ và đạo đức, phục vụ dân tộc và nhân loại" }
    ]
};

// Export the data for use in other files
if (typeof module !== 'undefined' && module.exports) {
    module.exports = flashcardsData;
}
