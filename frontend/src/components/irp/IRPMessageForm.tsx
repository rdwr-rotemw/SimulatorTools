import React from 'react'
import {Box, FormControlLabel, Switch, TextField, Typography,} from '@mui/material'

interface IRPMessageFormProps {
    messageData: Record<string, any>
    onChange: (data: Record<string, any>) => void
}

const IRPMessageForm: React.FC<IRPMessageFormProps> = ({messageData, onChange}) => {
    const handleFieldChange = (path: string[], value: any) => {
        const newData: Record<string, any> = {...messageData}
        let current: any = newData

        // Navigate to nested field
        for (let i = 0; i < path.length - 1; i++) {
            if (!current[path[i]]) current[path[i]] = {}
            current = current[path[i]]
        }

        // Set the value
        current[path[path.length - 1]] = value
        onChange(newData)
    }

    const renderField = (key: string, value: any, path: string[] = []): JSX.Element => {
        const currentPath = [...path, key]
        const pathString = currentPath.join('.')

        // Handle null/undefined
        if (value === null || value === undefined) {
            return (
                <TextField
                    key={pathString}
                    fullWidth
                    label={key}
                    value={''}
                    onChange={(e) => handleFieldChange(currentPath, e.target.value)}
                    margin="normal"
                    size="small"
                />
            )
        }

        // Boolean → Switch
        if (typeof value === 'boolean') {
            return (
                <FormControlLabel
                    key={pathString}
                    control={
                        <Switch
                            checked={value}
                            onChange={(e) => handleFieldChange(currentPath, e.target.checked)}
                        />
                    }
                    label={key}
                    sx={{marginY: 1}}
                />
            )
        }

        // Number → Number input with validation
        if (typeof value === 'number') {
            return (
                <TextField
                    key={pathString}
                    fullWidth
                    label={key}
                    type="number"
                    value={value}
                    onChange={(e) => {
                        const num = parseInt(e.target.value, 10)
                        handleFieldChange(currentPath, isNaN(num) ? 0 : num)
                    }}
                    margin="normal"
                    size="small"
                    error={isNaN(Number(value))}
                    helperText={isNaN(Number(value)) ? 'Must be a valid integer' : ''}
                />
            )
        }

        // Array → Render as JSON string (editable)
        if (Array.isArray(value)) {
            return (
                <TextField
                    key={pathString}
                    fullWidth
                    label={key}
                    value={JSON.stringify(value)}
                    onChange={(e) => {
                        try {
                            const parsed = JSON.parse(e.target.value)
                            handleFieldChange(currentPath, parsed)
                        } catch {
                            // Invalid JSON, keep as string
                        }
                    }}
                    margin="normal"
                    size="small"
                    multiline
                    helperText="Array (JSON format)"
                />
            )
        }

        // Object → Render nested fields recursively
        if (typeof value === 'object' && value !== null) {
            return (
                <Box key={pathString} sx={{marginY: 2, paddingLeft: 2, borderLeft: '2px solid #E0E0E0'}}>
                    <Typography variant="subtitle2" sx={{fontWeight: 'bold', marginBottom: 1}}>
                        {key}
                    </Typography>
                    {Object.keys(value).map((nestedKey) => renderField(nestedKey, value[nestedKey], currentPath))}
                </Box>
            )
        }

        // String → Text input (default)
        return (
            <TextField
                key={pathString}
                fullWidth
                label={key}
                value={String(value)}
                onChange={(e) => handleFieldChange(currentPath, e.target.value)}
                margin="normal"
                size="small"
            />
        )
    }

    return (
        <Box>
            {Object.keys(messageData).map((key) => (
                <React.Fragment key={key}>{renderField(key, messageData[key])}</React.Fragment>
            ))}
        </Box>
    )
}

export default IRPMessageForm

