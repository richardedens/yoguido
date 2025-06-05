// FIXED YoGuido JavaScript Runtime with Working Button Events
console.log("🚀 YoGuido JavaScript is loading...");

class YoGuidoApp {
    constructor() {
        console.log("🏗️ YoGuidoApp constructor called");
        this.state = {};
        this.eventHandlers = {};
        this.componentTree = [];
        this.buttonHandlers = new Map();
    }
    
    async init() {
        console.log("🎬 YoGuidoApp.init() called");
        
        // Hide loading, show app
        const loading = document.getElementById('loading');
        const appContent = document.getElementById('app-content');
        
        if (loading) {
            loading.style.display = 'none';
            console.log("✅ Hidden loading div");
        }
        
        if (appContent) {
            appContent.style.display = 'block';
            console.log("✅ Showed app content div");
        } else {
            console.log("❌ Could not find app-content div");
            return;
        }
        
        // Initial render
        console.log("🎨 Calling initial render...");
        await this.render();
    }
    
    async render() {
        try {
            console.log("🎨 Starting render...");
            
            const response = await fetch('/api/render', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            
            console.log("📡 /api/render response status:", response.status);
            
            if (!response.ok) {
                throw new Error(`Render failed: ${response.statusText}`);
            }
            
            const data = await response.json();
            console.log("📊 Render response data:", data);
            
            this.componentTree = data.component_tree || [];
            console.log("🌳 Component tree:", this.componentTree);
            
            this.renderComponentTree();
            
        } catch (error) {
            console.error("❌ Render error:", error);
            this.showError(error.message);
        }
    }
    
    renderComponentTree() {
        console.log("🖼️ Rendering component tree with", this.componentTree.length, "components");
        
        const container = document.getElementById('app-content');
        if (!container) {
            console.error("❌ Could not find app-content container!");
            return;
        }
        
        // Clear container
        container.innerHTML = '';
        
        // Clear existing button handlers
        this.buttonHandlers.clear();
        
        // Render each component
        this.componentTree.forEach((component, index) => {
            console.log(`🧩 Rendering component ${index}: ${component.type}`);
            try {
                const element = this.createElement(component);
                container.appendChild(element);
            } catch (error) {
                console.error(`❌ Failed to render component ${index}:`, error);
            }
        });
        
        console.log("✅ Component tree rendering complete");
        console.log(`🎯 Registered ${this.buttonHandlers.size} button handlers`);
    }
    
    createElement(componentData) {
        const { type, id, props, handlers } = componentData;
        
        switch (type) {
            case 'title':
                return this.createTitle(id, props);
            case 'text':
                return this.createText(id, props);
            case 'button':
                return this.createButton(id, props, handlers);
            case 'container':
                return this.createContainer(id, props, componentData.children || []);
            case 'input_text':
                return this.createInputText(id, props);
            case 'select':
                return this.createSelect(id, props);
            case 'checkbox':
                return this.createCheckbox(id, props);
            case 'table':
                return this.createTable(id, props);
            default:
                console.warn(`Unknown component type: ${type}`);
                const div = document.createElement('div');
                div.textContent = `Unknown component: ${type}`;
                return div;
        }
    }
    
    createTitle(id, props) {
        const level = props.level || 1;
        const element = document.createElement(`h${level}`);
        element.id = id;
        element.textContent = props.text || '';
        element.className = props.class_name || 'text-2xl font-bold text-gray-900 mb-4';
        return element;
    }
    
    createText(id, props) {
        const element = document.createElement('p');
        element.id = id;
        element.textContent = props.content || '';
        element.className = props.class_name || 'text-gray-600 mb-2';
        return element;
    }
    
    createButton(id, props, handlers) {
        console.log(`🔘 Creating button: ${id}`, props, handlers);
        
        const element = document.createElement('button');
        element.id = id;
        element.textContent = props.label || 'Button';
        element.className = props.class_name || 'bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600 transition-colors';
        
        // CRITICAL FIX: Add click handler if it exists
        if (handlers && handlers.click) {
            const handlerId = handlers.click;
            console.log(`🎯 Registering click handler for button ${id}: ${handlerId}`);
            
            // Store handler reference
            this.buttonHandlers.set(id, handlerId);
            
            // Add click event listener
            element.addEventListener('click', async (event) => {
                console.log(`🔥 Button clicked: ${id} -> ${handlerId}`);
                event.preventDefault();
                
                try {
                    // Send event to backend
                    await this.sendButtonClick(id, handlerId);
                } catch (error) {
                    console.error(`❌ Button click failed for ${id}:`, error);
                }
            });
            
            console.log(`✅ Click handler registered for button ${id}`);
        } else {
            console.log(`⚠️ No click handler for button ${id}`);
        }
        
        return element;
    }
    
    async sendButtonClick(buttonId, handlerId) {
        console.log(`📡 Sending button click: ${buttonId} -> ${handlerId}`);
        
        try {
            const response = await fetch('/hcc', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    event_type: 'click',
                    element_id: buttonId,
                    handler_id: handlerId,
                    timestamp: new Date().toISOString()
                })
            });
            
            console.log(`📡 Button click response status: ${response.status}`);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            console.log(`📊 Button click response:`, data);
            
            // If server returns updated component tree, re-render
            if (data.component_tree) {
                console.log("🔄 Re-rendering after button click...");
                this.componentTree = data.component_tree;
                this.renderComponentTree();
            }
            
            // Show any alerts or notifications
            if (data.status === 'success') {
                console.log("✅ Button click processed successfully");
            }
            
        } catch (error) {
            console.error(`❌ Failed to send button click:`, error);
            this.showError(`Button click failed: ${error.message}`);
        }
    }
    
    createContainer(id, props, children) {
        const element = document.createElement('div');
        element.id = id;
        element.className = props.class_name || 'p-6';
        
        children.forEach(child => {
            element.appendChild(this.createElement(child));
        });
        
        return element;
    }
    
    createInputText(id, props) {
        const element = document.createElement('input');
        element.type = 'text';
        element.id = id;
        element.placeholder = props.placeholder || '';
        element.value = props.value || '';
        element.className = props.class_name || 'border border-gray-300 rounded px-3 py-2';
        
        // Add input change handler
        element.addEventListener('input', async (event) => {
            await this.sendInputChange(id, event.target.value);
        });
        
        return element;
    }
    
    async sendInputChange(inputId, value) {
        try {
            const response = await fetch('/hcc', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    event_type: 'input',
                    element_id: inputId,
                    value: value,
                    timestamp: new Date().toISOString()
                })
            });
            
            if (response.ok) {
                const data = await response.json();
                console.log(`📝 Input change processed:`, data);
            }
        } catch (error) {
            console.error(`❌ Failed to send input change:`, error);
        }
    }
    
    createSelect(id, props) {
        const element = document.createElement('select');
        element.id = id;
        element.className = props.class_name || 'border border-gray-300 rounded px-3 py-2';
        
        (props.options || []).forEach(option => {
            const optionElement = document.createElement('option');
            optionElement.value = option.value || option;
            optionElement.textContent = option.label || option;
            if (props.value === optionElement.value) {
                optionElement.selected = true;
            }
            element.appendChild(optionElement);
        });
        
        // Add change handler
        element.addEventListener('change', async (event) => {
            await this.sendInputChange(id, event.target.value);
        });
        
        return element;
    }
    
    createCheckbox(id, props) {
        const wrapper = document.createElement('div');
        wrapper.className = props.class_name || 'flex items-center space-x-2';
        
        const element = document.createElement('input');
        element.type = 'checkbox';
        element.id = id;
        element.checked = props.checked || false;
        element.className = 'rounded';
        
        const label = document.createElement('label');
        label.htmlFor = id;
        label.textContent = props.label || '';
        label.className = 'text-sm font-medium text-gray-700';
        
        wrapper.appendChild(element);
        wrapper.appendChild(label);
        
        // Add change handler
        element.addEventListener('change', async (event) => {
            await this.sendInputChange(id, event.target.checked);
        });
        
        return wrapper;
    }
    
    createTable(id, props) {
        const wrapper = document.createElement('div');
        wrapper.className = 'overflow-x-auto';
        
        const table = document.createElement('table');
        table.id = id;
        table.className = props.class_name || 'w-full divide-y divide-gray-200';
        
        // Create header
        if (props.columns && props.columns.length > 0) {
            const thead = document.createElement('thead');
            thead.className = 'bg-gray-50';
            
            const headerRow = document.createElement('tr');
            props.columns.forEach(column => {
                const th = document.createElement('th');
                th.textContent = column.charAt(0).toUpperCase() + column.slice(1);
                th.className = 'px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider';
                headerRow.appendChild(th);
            });
            
            thead.appendChild(headerRow);
            table.appendChild(thead);
        }
        
        // Create body
        const tbody = document.createElement('tbody');
        tbody.className = 'bg-white divide-y divide-gray-200';
        
        (props.data || []).forEach((row, rowIndex) => {
            const tr = document.createElement('tr');
            tr.className = rowIndex % 2 === 0 ? 'bg-white' : 'bg-gray-50';
            
            (props.columns || Object.keys(row)).forEach(column => {
                const td = document.createElement('td');
                td.textContent = row[column] || '';
                td.className = 'px-6 py-4 whitespace-nowrap text-sm text-gray-900';
                tr.appendChild(td);
            });
            
            tbody.appendChild(tr);
        });
        
        table.appendChild(tbody);
        wrapper.appendChild(table);
        
        return wrapper;
    }
    
    showError(message) {
        console.error("🚨 Showing error:", message);
        const errorDisplay = document.getElementById('error-display');
        const errorMessage = document.getElementById('error-message');
        
        if (errorDisplay && errorMessage) {
            errorMessage.textContent = message;
            errorDisplay.classList.remove('hidden');
        }
    }
    
    // Debug method to inspect current state
    debugState() {
        console.log("🔍 DEBUG STATE:");
        console.log("   Component tree:", this.componentTree);
        console.log("   Button handlers:", this.buttonHandlers);
        console.log("   State:", this.state);
    }
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    console.log("📄 DOM loaded, initializing YoGuido app...");
    const app = new YoGuidoApp();
    app.init();
    
    // Make app globally available for debugging
    window.yoguidoApp = app;
    console.log("🌍 App available globally as window.yoguidoApp");
    
    // Add debug helper
    window.debugYoGuido = () => {
        app.debugState();
    };
    console.log("🔍 Debug helper available as window.debugYoGuido()");
});

console.log("✅ YoGuido JavaScript loaded successfully");