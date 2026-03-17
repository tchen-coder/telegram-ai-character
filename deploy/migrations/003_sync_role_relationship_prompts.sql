-- 同步角色关系提示词结构
-- 目标：
-- 1. 创建 role_relationship_prompts 表
-- 2. 将现有 roles 中的提示词统一迁移到 1/2/3 三档
-- 3. 让旧字段 system_prompt_friend/system_prompt_partner/system_prompt_lover 保持一致
-- 4. 将 user_roles.relationship 默认值调整为 3

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

ALTER TABLE `user_roles` MODIFY COLUMN `relationship` INT NOT NULL DEFAULT 3;

UPDATE `roles`
SET
  `system_prompt_friend` = COALESCE(NULLIF(`system_prompt_friend`, ''), `system_prompt`),
  `system_prompt_partner` = COALESCE(NULLIF(`system_prompt_friend`, ''), `system_prompt`),
  `system_prompt_lover` = COALESCE(NULLIF(`system_prompt_friend`, ''), `system_prompt`);

INSERT INTO `role_relationship_prompts`
  (`role_id`, `relationship`, `prompt_text`, `is_active`, `created_at`, `updated_at`)
SELECT
  `id`,
  1,
  COALESCE(NULLIF(`system_prompt_friend`, ''), `system_prompt`),
  TRUE,
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP
FROM `roles`
ON DUPLICATE KEY UPDATE
  `prompt_text` = VALUES(`prompt_text`),
  `is_active` = TRUE,
  `updated_at` = CURRENT_TIMESTAMP;

INSERT INTO `role_relationship_prompts`
  (`role_id`, `relationship`, `prompt_text`, `is_active`, `created_at`, `updated_at`)
SELECT
  `id`,
  2,
  COALESCE(NULLIF(`system_prompt_friend`, ''), `system_prompt`),
  TRUE,
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP
FROM `roles`
ON DUPLICATE KEY UPDATE
  `prompt_text` = VALUES(`prompt_text`),
  `is_active` = TRUE,
  `updated_at` = CURRENT_TIMESTAMP;

INSERT INTO `role_relationship_prompts`
  (`role_id`, `relationship`, `prompt_text`, `is_active`, `created_at`, `updated_at`)
SELECT
  `id`,
  3,
  COALESCE(NULLIF(`system_prompt_friend`, ''), `system_prompt`),
  TRUE,
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP
FROM `roles`
ON DUPLICATE KEY UPDATE
  `prompt_text` = VALUES(`prompt_text`),
  `is_active` = TRUE,
  `updated_at` = CURRENT_TIMESTAMP;
