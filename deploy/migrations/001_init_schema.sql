-- 初始化数据库表结构
-- 执行前请备份数据库

-- 1. 创建 roles 表（角色配置）
CREATE TABLE IF NOT EXISTS `roles` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `role_name` VARCHAR(100) NOT NULL UNIQUE,
  `system_prompt` TEXT NOT NULL,
  `system_prompt_friend` TEXT,
  `system_prompt_partner` TEXT,
  `system_prompt_lover` TEXT,
  `scenario` TEXT,
  `greeting_message` TEXT,
  `avatar_url` VARCHAR(500),
  `tags` JSON,
  `is_active` BOOLEAN DEFAULT TRUE,
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX `idx_role_active` (`is_active`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. 创建 role_relationship_prompts 表（关系等级提示词）
CREATE TABLE IF NOT EXISTS `role_relationship_prompts` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `role_id` INT NOT NULL,
  `relationship` INT NOT NULL DEFAULT 3,
  `prompt_text` TEXT NOT NULL,
  `is_active` BOOLEAN DEFAULT TRUE,
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (`role_id`) REFERENCES `roles`(`id`) ON DELETE CASCADE,
  UNIQUE KEY `uk_role_relationship_prompt` (`role_id`, `relationship`),
  INDEX `idx_role_relationship_prompt` (`role_id`, `relationship`, `is_active`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. 创建 role_images 表（角色图片资源）
CREATE TABLE IF NOT EXISTS `role_images` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `role_id` INT NOT NULL,
  `image_url` VARCHAR(500) NOT NULL,
  `image_type` VARCHAR(50) NOT NULL DEFAULT 'avatar',
  `stage_key` VARCHAR(50),
  `trigger_type` VARCHAR(50) NOT NULL DEFAULT 'manual',
  `sort_order` INT NOT NULL DEFAULT 0,
  `is_active` BOOLEAN DEFAULT TRUE,
  `meta_json` JSON,
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (`role_id`) REFERENCES `roles`(`id`) ON DELETE CASCADE,
  INDEX `idx_role_image_order` (`role_id`, `image_type`, `sort_order`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4. 创建 user_roles 表（用户-角色关系）
CREATE TABLE IF NOT EXISTS `user_roles` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `user_id` VARCHAR(50) NOT NULL,
  `role_id` INT NOT NULL,
  `relationship` INT NOT NULL DEFAULT 1,
  `is_current` BOOLEAN DEFAULT FALSE,
  `first_interaction_at` DATETIME,
  `last_interaction_at` DATETIME,
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (`role_id`) REFERENCES `roles`(`id`) ON DELETE CASCADE,
  UNIQUE KEY `uk_user_role` (`user_id`, `role_id`),
  INDEX `idx_user_current` (`user_id`, `is_current`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 5. 创建 chat_history 表（聊天记录）
CREATE TABLE IF NOT EXISTS `chat_history` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `user_id` VARCHAR(50) NOT NULL,
  `role_id` INT NOT NULL,
  `message_type` ENUM('user', 'assistant', 'assistant_image') NOT NULL,
  `content` TEXT NOT NULL,
  `image_url` VARCHAR(500),
  `emotion_data` JSON,
  `decision_data` JSON,
  `meta_json` JSON,
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (`role_id`) REFERENCES `roles`(`id`) ON DELETE CASCADE,
  INDEX `idx_user_role_time` (`user_id`, `role_id`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
