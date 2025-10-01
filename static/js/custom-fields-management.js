/**
 * Custom Fields Management JavaScript
 *
 * Handles all frontend functionality for managing custom fields in the settings page,
 * including CRUD operations, validation, and UI interactions.
 */

class CustomFieldsManager {
    constructor() {
        this.currentEditingFieldId = null;
        this.customFieldsData = [];
        this.apiBaseUrl = '/api/custom-fields';

        // Initialize when DOM is ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.init());
        } else {
            this.init();
        }
    }

    init() {
        this.setupEventListeners();
        this.loadCustomFields();
    }

    setupEventListeners() {
        // Add Custom Field button
        const addBtn = document.getElementById('add-custom-field-btn');
        if (addBtn) {
            addBtn.addEventListener('click', () => this.openCustomFieldModal());
        }

        // Save Custom Field button
        const saveBtn = document.getElementById('saveCustomFieldBtn');
        if (saveBtn) {
            saveBtn.addEventListener('click', () => this.saveCustomField());
        }

        // Confirm Delete button
        const deleteBtn = document.getElementById('confirmDeleteBtn');
        if (deleteBtn) {
            deleteBtn.addEventListener('click', () => this.confirmDeleteCustomField());
        }

        // Field Type change handler
        const fieldTypeSelect = document.getElementById('fieldType');
        if (fieldTypeSelect) {
            fieldTypeSelect.addEventListener('change', (e) => {
                this.toggleSelectOptions(e.target.value === 'select');
            });
        }

        // Field Name input validation
        const fieldNameInput = document.getElementById('fieldName');
        if (fieldNameInput) {
            fieldNameInput.addEventListener('input', (e) => this.validateFieldName(e.target));
            fieldNameInput.addEventListener('blur', (e) => this.generateLabelFromName(e.target));
        }

        // Modal cleanup on close
        const modal = document.getElementById('customFieldModal');
        if (modal) {
            modal.addEventListener('hidden.bs.modal', () => this.resetCustomFieldForm());
        }

        // Enter key handling in modal form
        const form = document.getElementById('customFieldForm');
        if (form) {
            form.addEventListener('keypress', (e) => {
                if (e.key === 'Enter' && e.target.type !== 'textarea') {
                    e.preventDefault();
                    this.saveCustomField();
                }
            });
        }
    }

    async loadCustomFields() {
        const loadingElement = document.getElementById('custom-fields-loading');
        const emptyElement = document.getElementById('custom-fields-empty');
        const listElement = document.getElementById('custom-fields-list');

        if (!loadingElement || !emptyElement || !listElement) {
            console.error('Required DOM elements not found for loading custom fields');
            return;
        }

        // Show loading state
        loadingElement.style.display = 'block';
        emptyElement.style.display = 'none';
        listElement.style.display = 'none';

        try {
            const response = await fetch(`${this.apiBaseUrl}/`, {
                method: 'GET',
                headers: {
                    'Accept': 'application/json'
                }
            });

            const data = await response.json();

            if (data.success) {
                this.customFieldsData = data.data || [];
                this.displayCustomFields(this.customFieldsData);
            } else {
                this.showError('Failed to load custom fields: ' + (data.message || 'Unknown error'));
            }
        } catch (error) {
            console.error('Error loading custom fields:', error);
            this.showError('Failed to load custom fields. Please check your connection and try again.');
        } finally {
            loadingElement.style.display = 'none';
        }
    }

    displayCustomFields(fields) {
        const emptyElement = document.getElementById('custom-fields-empty');
        const listElement = document.getElementById('custom-fields-list');
        const tbody = document.getElementById('custom-fields-tbody');

        if (!emptyElement || !listElement || !tbody) {
            console.error('Required DOM elements not found for displaying custom fields');
            return;
        }

        if (!fields || fields.length === 0) {
            emptyElement.style.display = 'block';
            listElement.style.display = 'none';
            return;
        }

        // Clear existing rows
        tbody.innerHTML = '';

        // Add each field as a row
        fields.forEach(field => {
            const row = this.createCustomFieldRow(field);
            tbody.appendChild(row);
        });

        emptyElement.style.display = 'none';
        listElement.style.display = 'block';
    }

    createCustomFieldRow(field) {
        const row = document.createElement('tr');

        const typeClass = `field-type-${field.field_type}`;
        const statusClass = field.is_active ? 'field-status-active' : 'field-status-inactive';
        const statusText = field.is_active ? 'Active' : 'Inactive';

        row.innerHTML = `
            <td>
                <div class="fw-bold">${this.escapeHtml(field.label)}</div>
                <small class="text-muted">${this.escapeHtml(field.name)}</small>
                ${field.description ? `<div class="text-muted small mt-1">${this.escapeHtml(field.description)}</div>` : ''}
            </td>
            <td>
                <span class="field-type-badge ${typeClass}">
                    ${field.field_type}
                </span>
            </td>
            <td>
                ${field.is_required ?
                    '<span class="badge bg-warning">Required</span>' :
                    '<span class="badge bg-secondary">Optional</span>'
                }
            </td>
            <td>
                <span class="${statusClass}">${statusText}</span>
            </td>
            <td>
                <small class="text-muted">
                    <i class="fas fa-chart-bar"></i> 0 positions
                </small>
            </td>
            <td>
                <div class="btn-group" role="group">
                    <button class="btn btn-sm btn-outline-primary" onclick="customFieldsManager.editCustomField(${field.id})" title="Edit Field">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-secondary" onclick="customFieldsManager.toggleFieldStatus(${field.id})" title="Toggle Active Status">
                        <i class="fas ${field.is_active ? 'fa-eye-slash' : 'fa-eye'}"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-danger" onclick="customFieldsManager.deleteCustomField(${field.id})" title="Delete Field">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </td>
        `;

        return row;
    }

    openCustomFieldModal(field = null) {
        this.currentEditingFieldId = field ? field.id : null;

        // Update modal title
        const modalTitle = document.getElementById('customFieldModalLabel');
        const saveButtonText = document.getElementById('saveButtonText');

        if (field) {
            modalTitle.textContent = 'Edit Custom Field';
            saveButtonText.textContent = 'Update Field';
            this.populateFormWithField(field);
        } else {
            modalTitle.textContent = 'Add Custom Field';
            saveButtonText.textContent = 'Create Field';
            this.resetCustomFieldForm();
        }

        // Show modal
        const modal = new bootstrap.Modal(document.getElementById('customFieldModal'));
        modal.show();
    }

    populateFormWithField(field) {
        document.getElementById('fieldName').value = field.name || '';
        document.getElementById('fieldLabel').value = field.label || '';
        document.getElementById('fieldType').value = field.field_type || '';
        document.getElementById('fieldDescription').value = field.description || '';
        document.getElementById('fieldRequired').checked = field.is_required || false;
        document.getElementById('fieldOrder').value = field.sort_order || 0;
        document.getElementById('fieldActive').checked = field.is_active !== false;
        document.getElementById('fieldDefault').value = field.default_value || '';

        // Handle select options if field type is select
        if (field.field_type === 'select' && field.options) {
            this.toggleSelectOptions(true);
            this.populateSelectOptions(field.options);
        } else {
            this.toggleSelectOptions(field.field_type === 'select');
        }
    }

    populateSelectOptions(options) {
        const container = document.getElementById('optionsContainer');
        if (!container) return;

        container.innerHTML = '';

        options.forEach(option => {
            const optionRow = this.createOptionRow(option.option_label, option.option_value);
            container.appendChild(optionRow);
        });

        // Add empty row if no options
        if (options.length === 0) {
            const optionRow = this.createOptionRow('', '');
            container.appendChild(optionRow);
        }
    }

    async saveCustomField() {
        const form = document.getElementById('customFieldForm');
        const saveButton = document.getElementById('saveCustomFieldBtn');
        const saveButtonText = document.getElementById('saveButtonText');
        const saveButtonSpinner = document.getElementById('saveButtonSpinner');

        if (!form || !saveButton) return;

        // Validate form
        if (!this.validateForm()) {
            return;
        }

        // Show loading state
        saveButton.disabled = true;
        saveButtonText.style.display = 'none';
        saveButtonSpinner.style.display = 'inline-block';

        try {
            const formData = this.collectFormData();
            const url = this.currentEditingFieldId
                ? `${this.apiBaseUrl}/${this.currentEditingFieldId}`
                : `${this.apiBaseUrl}/`;

            const method = this.currentEditingFieldId ? 'PUT' : 'POST';

            const response = await fetch(url, {
                method: method,
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify(formData)
            });

            const data = await response.json();

            if (data.success) {
                this.showSuccess(this.currentEditingFieldId ? 'Field updated successfully!' : 'Field created successfully!');

                // Close modal
                const modal = bootstrap.Modal.getInstance(document.getElementById('customFieldModal'));
                modal.hide();

                // Reload fields list
                await this.loadCustomFields();
            } else {
                this.showError('Failed to save field: ' + (data.message || 'Unknown error'));
            }
        } catch (error) {
            console.error('Error saving custom field:', error);
            this.showError('Failed to save field. Please check your connection and try again.');
        } finally {
            // Reset button state
            saveButton.disabled = false;
            saveButtonText.style.display = 'inline';
            saveButtonSpinner.style.display = 'none';
        }
    }

    collectFormData() {
        const formData = {
            name: document.getElementById('fieldName').value.trim(),
            label: document.getElementById('fieldLabel').value.trim(),
            field_type: document.getElementById('fieldType').value,
            description: document.getElementById('fieldDescription').value.trim(),
            is_required: document.getElementById('fieldRequired').checked,
            sort_order: parseInt(document.getElementById('fieldOrder').value) || 0,
            is_active: document.getElementById('fieldActive').checked,
            default_value: document.getElementById('fieldDefault').value.trim()
        };

        // Collect select options if field type is select
        if (formData.field_type === 'select') {
            const options = [];
            const optionRows = document.querySelectorAll('#optionsContainer .option-row');

            optionRows.forEach((row, index) => {
                const label = row.querySelector('input[name="option_label"]').value.trim();
                const value = row.querySelector('input[name="option_value"]').value.trim();

                if (label && value) {
                    options.push({
                        option_label: label,
                        option_value: value,
                        sort_order: index
                    });
                }
            });

            formData.options = options;
        }

        return formData;
    }

    validateForm() {
        let isValid = true;

        // Validate field name
        const fieldName = document.getElementById('fieldName');
        if (!this.validateFieldName(fieldName)) {
            isValid = false;
        }

        // Validate field label
        const fieldLabel = document.getElementById('fieldLabel');
        const fieldLabelError = document.getElementById('fieldLabelError');
        if (!fieldLabel.value.trim()) {
            fieldLabel.classList.add('is-invalid');
            fieldLabelError.textContent = 'Field label is required.';
            isValid = false;
        } else {
            fieldLabel.classList.remove('is-invalid');
            fieldLabelError.textContent = '';
        }

        // Validate field type
        const fieldType = document.getElementById('fieldType');
        if (!fieldType.value) {
            fieldType.classList.add('is-invalid');
            isValid = false;
        } else {
            fieldType.classList.remove('is-invalid');
        }

        // Validate select options if field type is select
        if (fieldType.value === 'select') {
            const optionRows = document.querySelectorAll('#optionsContainer .option-row');
            let hasValidOption = false;

            optionRows.forEach(row => {
                const label = row.querySelector('input[name="option_label"]').value.trim();
                const value = row.querySelector('input[name="option_value"]').value.trim();

                if (label && value) {
                    hasValidOption = true;
                }
            });

            if (!hasValidOption) {
                this.showError('Select fields must have at least one option with both label and value.');
                isValid = false;
            }
        }

        return isValid;
    }

    validateFieldName(input) {
        const fieldNameError = document.getElementById('fieldNameError');
        const value = input.value.trim();

        if (!value) {
            input.classList.add('is-invalid');
            fieldNameError.textContent = 'Field name is required.';
            return false;
        }

        // Check format: letters, numbers, underscores only, cannot start with number
        const nameRegex = /^[a-zA-Z_][a-zA-Z0-9_]*$/;
        if (!nameRegex.test(value)) {
            input.classList.add('is-invalid');
            fieldNameError.textContent = 'Field name must start with a letter or underscore and contain only letters, numbers, and underscores.';
            return false;
        }

        // Check if name already exists (excluding current editing field)
        const existingField = this.customFieldsData.find(field =>
            field.name.toLowerCase() === value.toLowerCase() &&
            field.id !== this.currentEditingFieldId
        );

        if (existingField) {
            input.classList.add('is-invalid');
            fieldNameError.textContent = 'A field with this name already exists.';
            return false;
        }

        input.classList.remove('is-invalid');
        fieldNameError.textContent = '';
        return true;
    }

    generateLabelFromName(nameInput) {
        const labelInput = document.getElementById('fieldLabel');

        // Only auto-generate if label is empty
        if (!labelInput.value.trim() && nameInput.value.trim()) {
            const label = nameInput.value
                .replace(/_/g, ' ')
                .replace(/\b\w/g, l => l.toUpperCase());
            labelInput.value = label;
        }
    }

    toggleSelectOptions(show) {
        const section = document.getElementById('selectOptionsSection');
        if (!section) return;

        if (show) {
            section.style.display = 'block';
            // Ensure at least one option row exists
            const container = document.getElementById('optionsContainer');
            if (container && container.children.length === 0) {
                this.addOption();
            }
        } else {
            section.style.display = 'none';
        }
    }

    addOption() {
        const container = document.getElementById('optionsContainer');
        if (!container) return;

        const optionRow = this.createOptionRow('', '');
        container.appendChild(optionRow);

        // Focus on the first input of the new row
        const labelInput = optionRow.querySelector('input[name="option_label"]');
        if (labelInput) {
            labelInput.focus();
        }
    }

    createOptionRow(label = '', value = '') {
        const div = document.createElement('div');
        div.className = 'option-row d-flex mb-2';

        div.innerHTML = `
            <input type="text" class="form-control me-2" placeholder="Option label" name="option_label" value="${this.escapeHtml(label)}">
            <input type="text" class="form-control me-2" placeholder="Option value" name="option_value" value="${this.escapeHtml(value)}">
            <button type="button" class="btn btn-outline-danger btn-sm" onclick="customFieldsManager.removeOption(this)">
                <i class="fas fa-times"></i>
            </button>
        `;

        // Add event listeners for auto-generating value from label
        const labelInput = div.querySelector('input[name="option_label"]');
        const valueInput = div.querySelector('input[name="option_value"]');

        if (labelInput && valueInput) {
            labelInput.addEventListener('blur', () => {
                if (labelInput.value.trim() && !valueInput.value.trim()) {
                    valueInput.value = labelInput.value.toLowerCase().replace(/\s+/g, '_');
                }
            });
        }

        return div;
    }

    removeOption(button) {
        const row = button.closest('.option-row');
        if (row) {
            row.remove();
        }
    }

    async editCustomField(fieldId) {
        const field = this.customFieldsData.find(f => f.id === fieldId);
        if (field) {
            this.openCustomFieldModal(field);
        } else {
            this.showError('Field not found. Please refresh the page and try again.');
        }
    }

    async toggleFieldStatus(fieldId) {
        try {
            const response = await fetch(`${this.apiBaseUrl}/${fieldId}/toggle-status`, {
                method: 'POST',
                headers: {
                    'Accept': 'application/json'
                }
            });

            const data = await response.json();

            if (data.success) {
                this.showSuccess('Field status updated successfully!');
                await this.loadCustomFields();
            } else {
                this.showError('Failed to update field status: ' + (data.message || 'Unknown error'));
            }
        } catch (error) {
            console.error('Error toggling field status:', error);
            this.showError('Failed to update field status. Please try again.');
        }
    }

    deleteCustomField(fieldId) {
        const field = this.customFieldsData.find(f => f.id === fieldId);
        if (!field) {
            this.showError('Field not found. Please refresh the page and try again.');
            return;
        }

        // Populate delete confirmation modal
        const deleteFieldInfo = document.getElementById('deleteFieldInfo');
        if (deleteFieldInfo) {
            deleteFieldInfo.innerHTML = `
                <strong>Field:</strong> ${this.escapeHtml(field.label)}<br>
                <strong>Type:</strong> ${field.field_type}<br>
                <strong>Name:</strong> ${this.escapeHtml(field.name)}
            `;
        }

        // Store field ID for deletion
        this.currentEditingFieldId = fieldId;

        // Show confirmation modal
        const modal = new bootstrap.Modal(document.getElementById('deleteCustomFieldModal'));
        modal.show();
    }

    async confirmDeleteCustomField() {
        if (!this.currentEditingFieldId) return;

        const deleteButton = document.getElementById('confirmDeleteBtn');
        const deleteButtonText = document.getElementById('deleteButtonText');
        const deleteButtonSpinner = document.getElementById('deleteButtonSpinner');

        // Show loading state
        deleteButton.disabled = true;
        deleteButtonText.style.display = 'none';
        deleteButtonSpinner.style.display = 'inline-block';

        try {
            const response = await fetch(`${this.apiBaseUrl}/${this.currentEditingFieldId}`, {
                method: 'DELETE',
                headers: {
                    'Accept': 'application/json'
                }
            });

            const data = await response.json();

            if (data.success) {
                this.showSuccess('Field deleted successfully!');

                // Close modal
                const modal = bootstrap.Modal.getInstance(document.getElementById('deleteCustomFieldModal'));
                modal.hide();

                // Reload fields list
                await this.loadCustomFields();
            } else {
                this.showError('Failed to delete field: ' + (data.message || 'Unknown error'));
            }
        } catch (error) {
            console.error('Error deleting custom field:', error);
            this.showError('Failed to delete field. Please try again.');
        } finally {
            // Reset button state
            deleteButton.disabled = false;
            deleteButtonText.style.display = 'inline';
            deleteButtonSpinner.style.display = 'none';
            this.currentEditingFieldId = null;
        }
    }

    resetCustomFieldForm() {
        const form = document.getElementById('customFieldForm');
        if (form) {
            form.reset();

            // Reset validation states
            form.querySelectorAll('.is-invalid').forEach(el => {
                el.classList.remove('is-invalid');
            });

            // Reset error messages
            form.querySelectorAll('.invalid-feedback').forEach(el => {
                el.textContent = '';
            });
        }

        // Reset select options section
        this.toggleSelectOptions(false);
        const optionsContainer = document.getElementById('optionsContainer');
        if (optionsContainer) {
            optionsContainer.innerHTML = '';
        }

        this.currentEditingFieldId = null;
    }

    // Utility methods
    escapeHtml(text) {
        if (!text) return '';
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.replace(/[&<>"']/g, m => map[m]);
    }

    showError(message) {
        // For now, use alert - can be enhanced with toast notifications
        alert('Error: ' + message);
        console.error('Custom Fields Error:', message);
    }

    showSuccess(message) {
        // For now, use alert - can be enhanced with toast notifications
        alert('Success: ' + message);
        console.log('Custom Fields Success:', message);
    }
}

// Initialize the custom fields manager when this script loads
const customFieldsManager = new CustomFieldsManager();

// Expose globally for onclick handlers
window.customFieldsManager = customFieldsManager;