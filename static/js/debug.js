// Arquivo de debug para verificar o carregamento dos templates
document.addEventListener('DOMContentLoaded', function() {
    console.log('=== DEBUG: Verificando sistema ===');
    
    // Verificar se os templates existem
    const requiredTemplates = [
        'instalacaoTemplate',
        'viaturaTemplate', 
        'empilhadeiraTemplate',
        'sistemaTemplate',
        'equipamentoTemplate'
    ];
    
    console.log('Verificando templates:');
    requiredTemplates.forEach(templateName => {
        const template = document.getElementById(templateName);
        if (template) {
            console.log(`✓ ${templateName}: OK`);
            console.log(`  Conteúdo:`, template.innerHTML.substring(0, 200) + '...');
        } else {
            console.error(`✗ ${templateName}: NÃO ENCONTRADO`);
        }
    });
    
    // Verificar se as funções globais estão disponíveis
    console.log('\nVerificando funções globais:');
    const requiredFunctions = [
        'addInstalacao',
        'addViatura',
        'addEmpilhadeira',
        'addSistemaSeguranca',
        'addEquipamentoUnitizacao'
    ];
    
    requiredFunctions.forEach(funcName => {
        if (typeof window[funcName] === 'function') {
            console.log(`✓ ${funcName}(): OK`);
        } else {
            console.error(`✗ ${funcName}(): NÃO DISPONÍVEL`);
        }
    });
    
    // Verificar containers
    console.log('\nVerificando containers:');
    const containers = ['instalacoesContainer', 'viaturasContainer'];
    containers.forEach(containerId => {
        const container = document.getElementById(containerId);
        if (container) {
            console.log(`✓ ${containerId}: OK`);
        } else {
            console.error(`✗ ${containerId}: NÃO ENCONTRADO`);
        }
    });
    
    console.log('\n=== DEBUG COMPLETO ===');
    
    // Adicionar botão de debug na interface
    const debugBtn = document.createElement('button');
    debugBtn.textContent = 'Debug';
    debugBtn.className = 'btn btn-outline btn-sm';
    debugBtn.style.position = 'fixed';
    debugBtn.style.bottom = '20px';
    debugBtn.style.right = '20px';
    debugBtn.style.zIndex = '9999';
    debugBtn.onclick = function() {
        console.log('=== TESTE MANUAL ===');
        
        // Testar adicionar instalação
        try {
            addInstalacao();
            console.log('✓ addInstalacao() executado');
        } catch (e) {
            console.error('✗ Erro em addInstalacao():', e);
        }
        
        // Testar adicionar viatura
        try {
            addViatura();
            console.log('✓ addViatura() executado');
        } catch (e) {
            console.error('✗ Erro em addViatura():', e);
        }
    };
    
    document.body.appendChild(debugBtn);
});
