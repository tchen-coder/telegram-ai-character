-- 数据库结构检查和修复脚本
-- 用于对比和修复现有表结构

-- 检查 roles 表是否缺少新增字段
ALTER TABLE `roles` ADD COLUMN IF NOT EXISTS `system_prompt_friend` TEXT;
ALTER TABLE `roles` ADD COLUMN IF NOT EXISTS `system_prompt_partner` TEXT;
ALTER TABLE `roles` ADD COLUMN IF NOT EXISTS `system_prompt_lover` TEXT;
ALTER TABLE `roles` ADD COLUMN IF NOT EXISTS `tags` JSON;

-- 检查 role_images 表是否存在
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

INSERT INTO `role_relationship_prompts` (`role_id`, `relationship`, `prompt_text`, `is_active`)
SELECT `id`, 1, COALESCE(NULLIF(`system_prompt_friend`, ''), `system_prompt`), TRUE
FROM `roles`
WHERE COALESCE(NULLIF(`system_prompt_friend`, ''), `system_prompt`) IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM `role_relationship_prompts` p
    WHERE p.`role_id` = `roles`.`id` AND p.`relationship` = 1
  );

INSERT INTO `role_relationship_prompts` (`role_id`, `relationship`, `prompt_text`, `is_active`)
SELECT `id`, 2, `system_prompt_partner`, TRUE
FROM `roles`
WHERE NULLIF(`system_prompt_partner`, '') IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM `role_relationship_prompts` p
    WHERE p.`role_id` = `roles`.`id` AND p.`relationship` = 2
  );

INSERT INTO `role_relationship_prompts` (`role_id`, `relationship`, `prompt_text`, `is_active`)
SELECT `id`, 3, `system_prompt_lover`, TRUE
FROM `roles`
WHERE NULLIF(`system_prompt_lover`, '') IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM `role_relationship_prompts` p
    WHERE p.`role_id` = `roles`.`id` AND p.`relationship` = 3
  );

-- 检查 role_images 表是否存在
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

-- 检查 user_roles 表是否存在
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

ALTER TABLE `user_roles` MODIFY COLUMN `relationship` INT NOT NULL DEFAULT 1;

-- 检查 chat_history 表字段
ALTER TABLE `chat_history` ADD COLUMN IF NOT EXISTS `image_url` VARCHAR(500);
ALTER TABLE `chat_history` ADD COLUMN IF NOT EXISTS `meta_json` JSON;

-- 修改 message_type 枚举值（如果已存在）
ALTER TABLE `chat_history` MODIFY COLUMN `message_type` ENUM('user', 'assistant', 'assistant_image') NOT NULL;

-- 添加索引（如果不存在）
ALTER TABLE `chat_history` ADD INDEX IF NOT EXISTS `idx_user_role_time` (`user_id`, `role_id`, `created_at`);
ALTER TABLE `roles` ADD INDEX IF NOT EXISTS `idx_role_active` (`is_active`);
