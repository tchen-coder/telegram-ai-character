-- 初始化数据库表结构
-- 执行前请备份数据库

CREATE TABLE IF NOT EXISTS `roles` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `role_id` INT NOT NULL,
  `role_name` VARCHAR(100) NOT NULL UNIQUE,
  `system_prompt` TEXT NOT NULL,
  `scenario` TEXT,
  `greeting_message` TEXT,
  `avatar_url` VARCHAR(500),
  `tags` JSON,
  `is_active` BOOLEAN DEFAULT TRUE,
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX `idx_role_active` (`is_active`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `role_relationship_prompts` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `role_id` INT NOT NULL,
  `relationship` INT NOT NULL DEFAULT 1,
  `prompt_text` TEXT NOT NULL,
  `is_active` BOOLEAN DEFAULT TRUE,
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (`role_id`) REFERENCES `roles`(`id`) ON DELETE CASCADE,
  UNIQUE KEY `uk_role_relationship_prompt` (`role_id`, `relationship`),
  INDEX `idx_role_relationship_prompt` (`role_id`, `relationship`, `is_active`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

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

CREATE TABLE IF NOT EXISTS `user_roles` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `user_id` VARCHAR(50) NOT NULL,
  `real_user_id` VARCHAR(50),
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

CREATE TABLE IF NOT EXISTS `chat_history` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `user_id` VARCHAR(50) NOT NULL,
  `role_id` INT NOT NULL,
  `group_seq` INT,
  `cur_relationship` INT NOT NULL DEFAULT 1,
  `timestamp` BIGINT NOT NULL,
  `message_type` ENUM('user', 'assistant', 'assistant_image') NOT NULL,
  `content` TEXT NOT NULL,
  `image_url` VARCHAR(500),
  `emotion_data` JSON,
  `decision_data` JSON,
  `meta_json` JSON,
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (`role_id`) REFERENCES `roles`(`id`) ON DELETE CASCADE,
  INDEX `idx_user_role_time` (`user_id`, `role_id`, `timestamp`),
  INDEX `idx_user_role_group_seq` (`user_id`, `role_id`, `group_seq`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `role_relationship_configs` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `role_id` INT NOT NULL,
  `initial_rv` INT NOT NULL DEFAULT 15,
  `update_frequency` INT NOT NULL DEFAULT 1,
  `max_negative_delta` INT NOT NULL DEFAULT 3,
  `max_positive_delta` INT NOT NULL DEFAULT 15,
  `recent_window_size` INT NOT NULL DEFAULT 12,
  `stage_names` JSON,
  `stage_floor_rv` JSON,
  `stage_thresholds` JSON,
  `paid_boost_enabled` BOOLEAN DEFAULT FALSE,
  `meta_json` JSON,
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (`role_id`) REFERENCES `roles`(`id`) ON DELETE CASCADE,
  UNIQUE KEY `uk_role_relationship_config` (`role_id`),
  INDEX `idx_role_relationship_config` (`role_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO `role_relationship_configs`
  (
    `role_id`, `initial_rv`, `update_frequency`, `max_negative_delta`,
    `max_positive_delta`, `recent_window_size`, `stage_names`, `stage_floor_rv`,
    `stage_thresholds`, `paid_boost_enabled`, `meta_json`, `created_at`, `updated_at`
  )
SELECT
  `id`,
  15,
  1,
  3,
  15,
  12,
  JSON_ARRAY('朋友', '恋人', '爱人'),
  JSON_ARRAY(0, 40, 70),
  JSON_ARRAY(40, 70, 100),
  FALSE,
  NULL,
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP
FROM `roles`
WHERE NOT EXISTS (
  SELECT 1
  FROM `role_relationship_configs` cfg
  WHERE cfg.`role_id` = `roles`.`id`
);
