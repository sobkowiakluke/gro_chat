-- Fresh schema for Gro Chat / MariaDB
-- Existing data migration is intentionally not included.

CREATE DATABASE IF NOT EXISTS flaskchat
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE flaskchat;

CREATE TABLE conversations (
    id INT NOT NULL AUTO_INCREMENT,
    title VARCHAR(255) NOT NULL DEFAULT 'Nowy chat',
    root_path VARCHAR(512) NULL,
    summary LONGTEXT NULL,
    summarized_until_message_id BIGINT NOT NULL DEFAULT 0,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    KEY idx_conversations_active_updated (is_deleted, updated_at)
) ENGINE=InnoDB;

CREATE TABLE llm_requests (
    id BIGINT NOT NULL AUTO_INCREMENT,
    conversation_id INT NOT NULL,

    provider VARCHAR(50) NOT NULL,
    model VARCHAR(150) NOT NULL,
    request_kind ENUM('chat', 'summary') NOT NULL DEFAULT 'chat',
    prompt_source VARCHAR(100) NULL,

    -- Exact messages array sent to the provider after popup edits.
    request_messages JSON NOT NULL,
    tokens_estimate INT NULL,

    status ENUM('pending', 'success', 'error') NOT NULL DEFAULT 'pending',
    tokens_in INT NULL,
    tokens_out INT NULL,
    latency_ms INT NULL,
    api_request_id VARCHAR(255) NULL,

    error_type VARCHAR(150) NULL,
    error_code VARCHAR(100) NULL,
    error_message LONGTEXT NULL,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME NULL,

    PRIMARY KEY (id),
    KEY idx_llm_requests_conversation (conversation_id, id),
    KEY idx_llm_requests_status_created (status, created_at),
    KEY idx_llm_requests_kind (request_kind),

    CONSTRAINT fk_llm_requests_conversation
        FOREIGN KEY (conversation_id)
        REFERENCES conversations(id)
        ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE messages (
    id BIGINT NOT NULL AUTO_INCREMENT,
    conversation_id INT NOT NULL,
    request_id BIGINT NULL,
    role ENUM('user', 'assistant') NOT NULL,
    content LONGTEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    KEY idx_messages_conversation_order (conversation_id, id),
    KEY idx_messages_request (request_id),
    FULLTEXT KEY ft_messages_content (content),

    CONSTRAINT fk_messages_conversation
        FOREIGN KEY (conversation_id)
        REFERENCES conversations(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_messages_request
        FOREIGN KEY (request_id)
        REFERENCES llm_requests(id)
        ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE conversation_prompt_memory (
    conversation_id INT NOT NULL,
    system_prompt LONGTEXT NOT NULL,
    summary LONGTEXT NOT NULL,
    facts LONGTEXT NOT NULL,
    decisions LONGTEXT NOT NULL,
    context LONGTEXT NOT NULL,
    history_json LONGTEXT NOT NULL,
    user_message LONGTEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (conversation_id),

    CONSTRAINT fk_prompt_memory_conversation
        FOREIGN KEY (conversation_id)
        REFERENCES conversations(id)
        ON DELETE CASCADE
) ENGINE=InnoDB;

-- The current code only reads workspace_items. This structure leaves room for
-- saved files, functions and folders without mixing them into chat history.
CREATE TABLE workspace_items (
    id BIGINT NOT NULL AUTO_INCREMENT,
    conversation_id INT NOT NULL,
    parent_id BIGINT NULL,
    item_type ENUM('folder', 'file', 'function', 'class', 'text') NOT NULL,
    name VARCHAR(255) NOT NULL,
    path VARCHAR(1024) NULL,
    content LONGTEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    KEY idx_workspace_conversation_parent (conversation_id, parent_id),

    CONSTRAINT fk_workspace_conversation
        FOREIGN KEY (conversation_id)
        REFERENCES conversations(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_workspace_parent
        FOREIGN KEY (parent_id)
        REFERENCES workspace_items(id)
        ON DELETE CASCADE
) ENGINE=InnoDB;
