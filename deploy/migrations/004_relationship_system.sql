-- 独立关系系统结构迁移
-- 目标：
-- 1. 建立角色级关系配置表
-- 2. 建立用户-角色关系状态表
-- 3. 建立关系事件日志表
-- 4. 回填已有 user_roles.relationship 到新状态表

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

ALTER TABLE `user_roles` MODIFY COLUMN `relationship` INT NOT NULL DEFAULT 1;

UPDATE `user_roles`
SET `relationship` = 1
WHERE `relationship` IS NULL OR `relationship` NOT IN (1, 2, 3);

CREATE TABLE IF NOT EXISTS `user_role_relationship_states` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `user_id` VARCHAR(50) NOT NULL,
  `role_id` INT NOT NULL,
  `current_rv` INT NOT NULL DEFAULT 15,
  `current_stage` INT NOT NULL DEFAULT 1,
  `max_unlocked_stage` INT NOT NULL DEFAULT 1,
  `last_rv` INT NOT NULL DEFAULT 15,
  `last_delta` INT NOT NULL DEFAULT 0,
  `last_update_at_turn` INT NOT NULL DEFAULT 0,
  `turn_count` INT NOT NULL DEFAULT 0,
  `update_frequency` INT NOT NULL DEFAULT 1,
  `pending_delta_accumulator` INT NOT NULL DEFAULT 0,
  `paid_boost_rv` INT NOT NULL DEFAULT 0,
  `paid_boost_applied` BOOLEAN DEFAULT FALSE,
  `paid_boost_source` VARCHAR(50),
  `emotion_summary_text` TEXT,
  `emotion_summary_updated_turn` INT NOT NULL DEFAULT 0,
  `emotion_adjustment_factor` DOUBLE NOT NULL DEFAULT 0.0,
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (`role_id`) REFERENCES `roles`(`id`) ON DELETE CASCADE,
  UNIQUE KEY `uk_user_role_relationship_state` (`user_id`, `role_id`),
  INDEX `idx_user_role_relationship_state` (`user_id`, `role_id`, `current_stage`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO `user_role_relationship_states`
  (
    `user_id`, `role_id`, `current_rv`, `current_stage`, `max_unlocked_stage`,
    `last_rv`, `last_delta`, `last_update_at_turn`, `turn_count`, `update_frequency`,
    `pending_delta_accumulator`, `paid_boost_rv`, `paid_boost_applied`,
    `paid_boost_source`, `emotion_summary_text`, `emotion_summary_updated_turn`,
    `emotion_adjustment_factor`, `created_at`, `updated_at`
  )
SELECT
  ur.`user_id`,
  ur.`role_id`,
  CASE
    WHEN COALESCE(ur.`relationship`, 1) >= 3 THEN GREATEST(COALESCE(cfg.`initial_rv`, 15), 70)
    WHEN COALESCE(ur.`relationship`, 1) = 2 THEN GREATEST(COALESCE(cfg.`initial_rv`, 15), 40)
    ELSE GREATEST(COALESCE(cfg.`initial_rv`, 15), 15)
  END,
  CASE
    WHEN COALESCE(ur.`relationship`, 1) IN (1, 2, 3) THEN ur.`relationship`
    ELSE 1
  END,
  CASE
    WHEN COALESCE(ur.`relationship`, 1) IN (1, 2, 3) THEN ur.`relationship`
    ELSE 1
  END,
  CASE
    WHEN COALESCE(ur.`relationship`, 1) >= 3 THEN GREATEST(COALESCE(cfg.`initial_rv`, 15), 70)
    WHEN COALESCE(ur.`relationship`, 1) = 2 THEN GREATEST(COALESCE(cfg.`initial_rv`, 15), 40)
    ELSE GREATEST(COALESCE(cfg.`initial_rv`, 15), 15)
  END,
  0,
  0,
  0,
  COALESCE(cfg.`update_frequency`, 1),
  0,
  0,
  FALSE,
  NULL,
  NULL,
  0,
  0.0,
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP
FROM `user_roles` ur
LEFT JOIN `role_relationship_configs` cfg ON cfg.`role_id` = ur.`role_id`
WHERE NOT EXISTS (
  SELECT 1
  FROM `user_role_relationship_states` state
  WHERE state.`user_id` = ur.`user_id` AND state.`role_id` = ur.`role_id`
);

CREATE TABLE IF NOT EXISTS `user_role_relationship_events` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `user_id` VARCHAR(50) NOT NULL,
  `role_id` INT NOT NULL,
  `trigger_message_id` INT NULL,
  `turn_index` INT NOT NULL DEFAULT 0,
  `triggered_update` BOOLEAN DEFAULT FALSE,
  `delta` INT NOT NULL DEFAULT 0,
  `pending_before` INT NOT NULL DEFAULT 0,
  `applied_delta` INT NOT NULL DEFAULT 0,
  `rv_before` INT NOT NULL DEFAULT 15,
  `rv_after` INT NOT NULL DEFAULT 15,
  `stage_before` INT NOT NULL DEFAULT 1,
  `stage_after` INT NOT NULL DEFAULT 1,
  `scoring_source` VARCHAR(50),
  `reason_text` TEXT,
  `payload_json` JSON,
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (`role_id`) REFERENCES `roles`(`id`) ON DELETE CASCADE,
  FOREIGN KEY (`trigger_message_id`) REFERENCES `chat_history`(`id`) ON DELETE SET NULL,
  INDEX `idx_user_role_relationship_event` (`user_id`, `role_id`, `turn_index`),
  INDEX `idx_relationship_event_message` (`trigger_message_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
